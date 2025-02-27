import discord
import re
import io
from ._list_plugin import issue_list, pull_request_list  # noqa
from discord.ext import commands
from typing import Optional
from lib.utils.decorators import normalize_repository, gitbot_group
from lib.utils.regex import MARKDOWN_EMOJI_RE
from lib.typehints import GitHubRepository
from lib.structs import GitBotEmbed, GitBot
from lib.structs.discord.context import GitBotContext


class Repo(commands.Cog):
    def __init__(self, bot: GitBot):
        self.bot: GitBot = bot

    @gitbot_group(name='repo', aliases=['r'], invoke_without_command=True)
    @normalize_repository
    async def repo_command_group(self, ctx: GitBotContext, repo: Optional[GitHubRepository] = None) -> None:
        if not repo:
            stored: Optional[str] = await self.bot.mgr.db.users.getitem(ctx, 'repo')
            if stored:
                ctx.invoked_with_stored = True
                await ctx.invoke(self.repo_info_command, repo=stored)
            else:
                await ctx.error(ctx.l.generic.nonexistent.repo.qa)
        else:
            await ctx.invoke(self.repo_info_command, repo=repo)

    @repo_command_group.command(name='info', aliases=['i'])
    @commands.cooldown(15, 30, commands.BucketType.user)
    @normalize_repository
    async def repo_info_command(self, ctx: GitBotContext, repo: Optional[GitHubRepository] = None) -> None:
        if not repo:
            return await ctx.invoke(self.repo_command_group)
        ctx.fmt.set_prefix('repo info')
        if ctx.data:
            r: dict = getattr(ctx, 'data')
        else:
            r: Optional[dict] = await self.bot.github.get_repo(repo)
        if not r:
            if ctx.invoked_with_stored:
                await self.bot.mgr.db.users.delitem(ctx, 'repo')
                await ctx.error(ctx.l.generic.nonexistent.repo.qa_changed)
            else:
                await ctx.error(ctx.l.generic.nonexistent.repo.base)
            return

        embed: GitBotEmbed = GitBotEmbed(
            color=int(r['primaryLanguage']['color'][1:], 16) if r['primaryLanguage'] and r['primaryLanguage']['color'] else self.bot.mgr.c.rounded,
            title=repo,
            url=r['url'],
            thumbnail=r['owner']['avatarUrl']
        )

        watch: int = r['watchers']['totalCount']
        star: int = r['stargazers']['totalCount']
        open_issues: int = r['issues']['totalCount']

        if r['description'] is not None and len(r['description']) != 0:
            embed.add_field(name=f":notepad_spiral: {ctx.l.repo.info.glossary[0]}:",
                            value=f"```{re.sub(MARKDOWN_EMOJI_RE, '', r['description']).strip()}```")

        watchers: str = ctx.fmt('watchers plural', watch, f"{r['url']}/watchers") if watch != 1 else ctx.fmt('watchers singular', f"{r['url']}/watchers")
        if watch == 0:
            watchers: str = ctx.l.repo.info.watchers.no_watchers
        stargazers: str = ctx.l.repo.info.stargazers.no_stargazers + '\n' if star == 0 else ctx.fmt('stargazers plural', star, f"{r['url']}/stargazers") + '\n'
        if star == 1:
            stargazers: str = ctx.fmt('stargazers singular', f"{r['url']}/stargazers") + '\n'

        watchers_stargazers: str = f"{watchers} {ctx.l.repo.info.linking_word} {stargazers}"

        issues: str = f'{ctx.l.repo.info.issues.no_issues}\n' if open_issues == 0 else ctx.fmt('issues plural',
                                                                                               open_issues,
                                                                                               f"{r['url']}/issues") + '\n'
        if open_issues == 1:
            issues: str = ctx.fmt('issues singular', f"{r['url']}/issues") + '\n'

        forks: str = ctx.l.repo.info.forks.no_forks + '\n' if r[
                                                                  'forkCount'] == 0 else ctx.fmt('forks plural', r['forkCount'], f"{r['url']}/network/members") + '\n'
        if r['forkCount'] == 1:
            forks: str = ctx.fmt('forks singular', f"{r['url']}/network/members") + '\n'
        forked = ""
        if 'isFork' in r and r['isFork'] is True:
            forked = ctx.fmt('fork_notice', f"[{r['parent']['nameWithOwner']}]({r['parent']['url']})") + '\n'

        created_at = ctx.fmt('created_at', self.bot.mgr.github_to_discord_timestamp(r['createdAt'])) + '\n'

        languages = ""
        if lang := r['primaryLanguage']:
            if r['languages'] == 1:
                languages = ctx.fmt('languages main', lang['name'])
            else:
                languages = ctx.fmt('languages with_num', r['languages'], lang['name'])

        info: str = f"{created_at}{issues}{forks}{watchers_stargazers}{forked}{languages}"
        embed.add_field(name=f":mag_right: {ctx.l.repo.info.glossary[1]}:", value=info)

        homepage: tuple = (r['homepageUrl'] if 'homepageUrl' in r and r['homepageUrl'] else None, ctx.l.repo.info.glossary[4])
        links: list = [homepage]
        link_strings: list = []
        for lnk in links:
            if lnk[0] is not None and len(lnk[0]) != 0:
                link_strings.append(f"- [{lnk[1]}]({lnk[0]})")
        if len(link_strings) != 0:
            embed.add_field(name=f":link: {ctx.l.repo.info.glossary[2]}:", value='\n'.join(link_strings))

        if topics := self.bot.mgr.render_label_like_list(r['topics'][0],
                                                name_and_url_knames_if_dict=('topic name', 'url'),
                                                total_n=r['topics'][1]):
            embed.add_field(name=f':label: {ctx.l.repo.info.glossary[3]}:', value=topics)

        if r['graphic']:
            embed.set_image(url=r['graphic'])

        if 'licenseInfo' in r and r['licenseInfo'] is not None and r['licenseInfo']["name"].lower() != 'other':
            embed.set_footer(text=ctx.fmt('license', r["licenseInfo"]["name"]))

        await ctx.send(embed=embed)

    @commands.cooldown(15, 30, commands.BucketType.user)
    @repo_command_group.command(name='files', aliases=['src', 'fs'])
    async def repo_files_command(self, ctx: GitBotContext, repo_or_path: GitHubRepository) -> None:
        ctx.fmt.set_prefix('repo files')
        is_tree: bool = False
        if repo_or_path.count('/') > 1:
            repo: GitHubRepository = '/'.join(repo_or_path.split('/', 2)[:2])  # noqa
            file: str = repo_or_path[len(repo):]
            src: list = await self.bot.github.get_tree_file(repo, file)
            is_tree: bool = True
        else:
            src = await self.bot.github.get_repo_files(repo_or_path)
        if not src:
            if is_tree:
                await ctx.error(ctx.l.generic.nonexistent.path)
            else:
                await ctx.error(ctx.l.generic.nonexistent.repo.base)
            return
        if is_tree and not isinstance(src, list):
            await ctx.error(ctx.fmt('not_a_directory', f'`{ctx.prefix}snippet`'))
            return
        files: list = sorted([f'{self.bot.mgr.e.file}  [{f["name"]}]({f["html_url"]})' if f['type'] == 'file' else
                              f'{self.bot.mgr.e.folder}  [{f["name"]}]({f["html_url"]})' for f in src[:15]],
                             key=lambda fs: 'file' in fs)
        if is_tree:
            link: str = str(src[0]['_links']['html'])
            link = link[:link.rindex('/')]
        else:
            link: str = f'https://github.com/{repo_or_path}'
        embed = discord.Embed(
            color=self.bot.mgr.c.rounded,
            title=f'`{repo_or_path}`' if len(repo_or_path) <= 60 else '/'.join(repo_or_path.split('/', 2)[:2]),
            description='\n'.join(files),
            url=link
        )
        if len(src) > 15:
            embed.set_footer(text=ctx.fmt('view_more', len(src) - 15))
        await ctx.send(embed=embed)

    @repo_command_group.command(name='download', aliases=['dl'])
    @commands.max_concurrency(10)
    @commands.cooldown(5, 30, commands.BucketType.user)
    @normalize_repository
    async def download_command(self, ctx: GitBotContext, repo: GitHubRepository) -> None:
        ctx.fmt.set_prefix('repo download')
        msg: discord.Message = await ctx.send(f"{self.bot.mgr.e.github}  {ctx.l.repo.download.wait}")
        src_bytes: Optional[bytes | bool] = await self.bot.github.get_repo_zip(repo)
        if src_bytes is None:  # pylint: disable=no-else-return
            return await msg.edit(content=f"{self.bot.mgr.e.err}  {ctx.l.generic.nonexistent.repo}")
        elif src_bytes is False:
            return await msg.edit(
                content=f"{self.bot.mgr.e.err}  {ctx.fmt('file_too_big', f'https://github.com/{repo}')}")
        io_obj: io.BytesIO = io.BytesIO(src_bytes)
        try:
            await ctx.send(file=discord.File(filename=f'{repo.replace("/", "-")}.zip', fp=io_obj))
            await msg.edit(content=f'{self.bot.mgr.e.checkmark}  {ctx.fmt("done", repo)}')
        except discord.errors.HTTPException:
            await msg.edit(
                content=f"{self.bot.mgr.e.err}  {ctx.fmt('file_too_big', f'https://github.com/{repo}')}")

    @repo_command_group.command(name='issues')
    @commands.cooldown(5, 40, commands.BucketType.user)
    @normalize_repository
    async def issue_list_command(self,
                                 ctx: GitBotContext,
                                 repo: Optional[GitHubRepository] = None,
                                 state: str = 'open') -> None:
        await issue_list(ctx, repo, state)

    @repo_command_group.command(name='pulls', aliases=['prs', 'pull', 'pr'])
    @commands.cooldown(5, 40, commands.BucketType.user)
    @normalize_repository
    async def pull_request_list_command(self,
                                        ctx: GitBotContext,
                                        repo: Optional[GitHubRepository] = None,
                                        state: str = 'open') -> None:
        await pull_request_list(ctx, repo, state)

    # signature from cogs.github.numbered.commits.Commits.commits
    @repo_command_group.command(name='commits')
    @commands.cooldown(5, 40, commands.BucketType.user)
    async def commit_list_command(self,
                                  ctx: GitBotContext,
                                  repo: Optional[GitHubRepository] = None) -> None:
        await ctx.invoke(self.bot.get_command('commits'), repo=repo)

    @repo_command_group.command(name='loc')
    @commands.cooldown(8, 60)
    async def loc_command(self, ctx: GitBotContext, repo: GitHubRepository) -> None:
        await ctx.invoke(self.bot.get_command('loc'), repo=repo)


async def setup(bot: GitBot) -> None:
    await bot.add_cog(Repo(bot))

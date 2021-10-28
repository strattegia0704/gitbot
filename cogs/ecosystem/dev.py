from discord.ext import commands
from typing import Optional
from lib.globs import Mgr
from lib.structs import GitBotEmbed
from lib.utils.decorators import gitbot_group


class Dev(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @gitbot_group('dev')
    @commands.cooldown(10, 60, commands.BucketType.user)
    async def dev_command_group(self, ctx: commands.Context) -> None:
        ctx.fmt.set_prefix('dev default')
        if ctx.invoked_subcommand is None:
            commands_: list = [
                f'`git dev --missing-locales` - {ctx.l.dev.default.commands.missing_locales}'
            ]
            embed: GitBotEmbed = GitBotEmbed(
                color=0x0384fc,
                title=ctx.l.dev.default.title,
                url='https://github.com/statch/gitbot',
                description=(ctx.l.dev.default.description
                             + f'\n{"⎯" * (len(ctx.l.dev.default.title) * 2)}\n'
                             + '\n'.join(commands_)),
                footer=ctx.l.dev.default.footer
            )
            await ctx.send(embed=embed)

    @dev_command_group.command('missing-locales')
    @commands.cooldown(10, 60, commands.BucketType.user)
    async def missing_locales_command(self, ctx: commands.Context, locale_: str) -> None:
        ctx.fmt.set_prefix('dev missing_locales')
        locale_data: Optional[tuple[list[str]], dict, bool] = Mgr.get_missing_keys_for_locale(locale_)
        if not locale_data:
            await ctx.err(ctx.l.generic.nonexistent.locale)
        elif not locale_data[0]:
            if locale_data[1]['name'] == Mgr.locale.master.meta.name:
                await ctx.err(ctx.fmt('no_master_locale', f'`{locale_data[1]["name"]}`'))
            else:
                await ctx.send(ctx.l.dev.missing_locales.no_missing_keys)
        else:
            def _gen_locale_path(steps) -> str:
                return ' **->** '.join([f'`{step}`' for step in steps])
            meta, _ = Mgr.get_locale_meta_by_attribute(locale_)
            missing: list[tuple[str]] = locale_data[0]
            embed: GitBotEmbed = GitBotEmbed(
                color=0x0384fc,
                title=ctx.fmt('title', meta['name']),
                url=f'https://github.com/statch/gitbot/blob/main/data/locale/{meta["name"]}.json',
                description='\n'.join([f'{Mgr.e.square} {_gen_locale_path(path)}' for path in missing])
            )
            await ctx.send(embed=embed)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Dev(bot))

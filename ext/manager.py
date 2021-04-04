import json
import re
import os
import functools
import operator
from motor.motor_asyncio import AsyncIOMotorClient
from discord.ext import commands
from ext.types import IterableDictSequence
from ext.structs import DirProxy, JSONProxy, GitCommandData
from ext import regex as r
from typing import Optional, Union, Callable, Any, Reversible, List, Iterable
from fuzzywuzzy import fuzz


class Manager:
    def __init__(self, github_instance):
        self.git = github_instance
        self.db: AsyncIOMotorClient = AsyncIOMotorClient(os.getenv('DB_CONNECTION')).store
        self.e: JSONProxy = self.load_json('emoji')
        self.l: DirProxy = DirProxy('data/locale/', '.json', exclude='index.json')
        self.locale: JSONProxy = self.load_json('locale/index')
        self.licenses: JSONProxy = self.load_json('licenses')
        self.patterns: tuple = ((r.GITHUB_LINES_RE, 'lines'),
                                (r.GITLAB_LINES_RE, 'lines'),
                                (r.ISSUE_RE, 'issue'),
                                (r.PR_RE, 'pr'),
                                (r.REPO_RE, 'repo'),
                                (r.USER_ORG_RE, 'user_org'))
        self.type_to_func: dict = {'repo': self.git.get_repo,
                                   'user_org': None,
                                   'issue': self.git.get_issue,
                                   'pr': self.git.get_pull_request,
                                   'lines': 'lines'}
        self.locale_cache: dict = {}
        setattr(self.locale, 'master', self.get_by_key_from_sequence(self.l, 'meta name', 'en'))
        self.__fix_missing_locales()

    def correlate_license(self, to_match: str) -> Optional[dict]:
        for i in list(self.licenses):
            match = fuzz.token_set_ratio(to_match, i['name'])
            match1 = fuzz.token_set_ratio(to_match, i['key'])
            match2 = fuzz.token_set_ratio(to_match, i['spdx_id'])
            if any([match > 80, match1 > 80, match2 > 80]):
                return i
        return None

    def load_json(self, name: str) -> JSONProxy:
        to_load = './data/' + str(name).lower() + '.json' if name[-5:] != '.json' else ''
        with open(to_load, 'r') as fp:
            data: Union[dict, list] = json.load(fp)
        return JSONProxy(data)

    async def get_link_reference(self, link: str) -> Optional[Union[GitCommandData, str, tuple]]:
        for pattern in self.patterns:
            match: list = re.findall(pattern[0], link)
            if match:
                match: Union[str, tuple] = match[0]
                action: Optional[Union[Callable, str]] = self.type_to_func[pattern[1]]
                if isinstance(action, str):
                    return GitCommandData(link, 'lines', link)
                if isinstance(match, tuple) and action:
                    match: tuple = tuple(i if not i.isnumeric() else int(i) for i in match)
                    obj: Union[dict, str] = await action(match[0], int(match[1]))
                    if isinstance(obj, str):
                        return obj, pattern[1]
                    return GitCommandData(obj, pattern[1], match)
                if not action:
                    if (obj := await self.git.get_user((m := match))) is None:
                        obj: Optional[dict] = await self.git.get_org(m)
                        return GitCommandData(obj, 'org', m) if obj is not None else 'no-user-or-org'
                    return GitCommandData(obj, 'user', m)
                repo = await action(match)
                return GitCommandData(repo, pattern[1], match) if repo is not None else 'repo'
        return None

    async def get_most_common(self, items: list) -> Any:
        return max(set(items), key=items.count)

    async def validate_number(self, number: str, items: List[dict]) -> Optional[dict]:
        if number.startswith('#'):
            number: str = number[1:]
        try:
            number: int = int(number)
        except (TypeError, ValueError):
            return None
        matched = [i for i in items if i['number'] == number]
        if matched:
            return matched[0]
        return None

    async def reverse(self, __sequence: Optional[Reversible]) -> Optional[Iterable]:
        if __sequence:
            return type(__sequence)(reversed(__sequence))
        return None

    async def readdir(self, path: str, ext: Union[str, list, tuple]) -> DirProxy:
        return DirProxy(path=path, ext=ext)

    async def error(self, ctx: commands.Context, msg: str) -> None:
        await ctx.send(f'{self.e.err}  {msg}')

    async def get_locale(self, ctx: commands.Context) -> JSONProxy:
        locale: str = 'en'
        if cached := self.locale_cache.get(ctx.author.id, None):
            locale = cached
        else:
            stored: Optional[dict] = await self.db.users.find_one({'_id': ctx.author.id})
            if stored is not None and (sl := stored.get('locale', None)):
                locale: str = sl
                self.locale_cache[ctx.author.id] = locale
        return getattr(self.l, locale)

    def get_nested_key(self, __d: Union[dict, JSONProxy], __k: Union[Iterable[str]]) -> Any:
        return functools.reduce(operator.getitem, __k, __d)

    def get_by_key_from_sequence(self,
                                 __sequence: IterableDictSequence,
                                 key: str,
                                 value: Any) -> Optional[Union[dict, JSONProxy]]:
        if len((_key := key.split())) > 1:
            key: list = _key
        for d in __sequence:
            if isinstance(key, str):
                if key in d and d[key] == value:
                    return d
            else:
                if self.get_nested_key(d, key) == value:
                    return d
        return None

    def __fix_missing_locales(self):
        def _recursively_fix(node: JSONProxy, ref: JSONProxy) -> JSONProxy:
            for k, v in ref.items():  # Surface fix
                if k not in node:
                    node[k] = v
            for k, v in node.items():
                if isinstance(v, (JSONProxy, dict)):
                    node[k] = _recursively_fix(v, ref[k])
            return node

        for locale in self.l:
            if locale != self.locale.master and 'meta' in locale:
                setattr(self.l, locale.meta.name, _recursively_fix(locale, self.locale.master))

import discord
from typing import Type
from discord.ext import commands
from lib.typehints.db.user import GitBotUser
from lib.typehints.db.guild.guild import GitBotGuild
from lib.structs import DictProxy, DirProxy, CaseInsensitiveDict, MaxAgeDict, FixedSizeOrderedDict
from lib.typehints.db.guild.release_feed import ReleaseFeedRepo, ReleaseFeedItem, ReleaseFeed, TagNameUpdateData
from lib.typehints.db.guild.autoconv import AutomaticConversion
from lib.typehints.generic import (GitHubRepository, GuildID,
                                   TagName, GitHubUser,
                                   GitHubOrganization, PyPIProject,
                                   Hash, MessageAttachmentURL,
                                   LocaleName)
from lib.typehints.locale.help import CommandHelp, ArgumentExplainer

__all__: tuple = (
    'DictSequence',
    'AnyDict',
    'Identity',
    'ReleaseFeedRepo',
    'ReleaseFeedItem',
    'ReleaseFeed',
    'GitHubRepository',
    'GuildID',
    'GitBotGuild',
    'TagName',
    'TagNameUpdateData',
    'GitHubUser',
    'GitHubOrganization',
    'PyPIProject',
    'AutomaticConversion',
    'Hash',
    'MessageAttachmentURL',
    'EmbedLike',
    'GitBotUser',
    'LocaleName',
    'CommandHelp',
    'ArgumentExplainer'
)

AnyDict = dict | DictProxy | CaseInsensitiveDict | MaxAgeDict | FixedSizeOrderedDict
DictSequence = tuple[AnyDict] | list[AnyDict] | DirProxy
Identity = int | str | commands.Context
EmbedLike = discord.Embed | Type['lib.structs.discord.gitbot_embed.GitBotEmbed']

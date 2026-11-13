"""watgbridge 配置项的图形化表单定义与默认值。"""

import copy

DATA_DIR_PLACEHOLDER = "{DATA}"

# 生成新配置文件时使用的默认值（基于 watgbridge sample_config.yaml）
DEFAULT_CONFIG = {
    "time_zone": "Asia/Shanghai",
    "time_format": "2006-01-02 15:04:05",
    "git_executable": "/usr/bin/git",
    "go_executable": "/usr/bin/go",
    "ffmpeg_executable": "/usr/bin/ffmpeg",
    "debug_mode": False,
    "use_github_binaries": False,
    "architecture": "",
    "telegram": {
        "bot_token": "",
        "api_url": "",
        "self_hosted_api": False,
        "send_images_as_file": False,
        "send_stickers_as_file": False,
        "owner_id": 0,
        "sudo_users_id": [],
        "target_chat_id": 0,
        "skip_video_stickers": False,
        "skip_setting_commands": False,
        "send_my_presence": False,
        "send_my_read_receipts": False,
        "silent_confirmation": True,
        "confirmation_type": "emoji",
        "skip_startup_message": False,
        "spoiler_as_viewonce": True,
        "reactions": True,
        "tag_all_enabled": False,
        "auto_react_when_all_read": True,
        "auto_react_remove_after_seconds": 0,
    },
    "backup": {
        "mode": "none",
        "cron_schedule": "0 3 * * *",
        "thread_name": "Database Backups",
    },
    "whatsapp": {
        "session_name": "watgbridge",
        "client_mode": "android",
        "tag_all_allowed_groups": [],
        "ignore_chats": [],
        "status_ignored_chats": [],
        "skip_documents": False,
        "skip_images": False,
        "skip_gifs": False,
        "skip_videos": False,
        "skip_voice_notes": False,
        "skip_audios": False,
        "skip_stickers": False,
        "skip_status": False,
        "skip_contacts": False,
        "skip_locations": False,
        "skip_profile_picture_updates": False,
        "skip_group_settings_updates": False,
        "skip_chat_details": True,
        "send_revoked_message_updates": False,
        "send_edited_message_updates": True,
        "whatsmeow_debug_mode": False,
        "send_my_messages_from_other_devices": False,
        "create_thread_for_info_updates": False,
        "skip_pinned_messages": False,
        "status_message_duration_seconds": 86400,
        "skip_offline_backlog": False,
        "login_database": {
            "type": "sqlite3",
            "url": f"file:{DATA_DIR_PLACEHOLDER}/bridge/wawebstore.db?_foreign_keys=on",
        },
        "sticker_metadata": {"pack_name": "WaTgBridge", "author_name": "WaTgBridge"},
    },
    "database": {"type": "sqlite", "path": f"{DATA_DIR_PLACEHOLDER}/bridge/gobot.sqlite.db"},
}


def default_config(data_dir: str) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)

    def fill(node):
        if isinstance(node, dict):
            return {k: fill(v) for k, v in node.items()}
        if isinstance(node, str):
            return node.replace(DATA_DIR_PLACEHOLDER, data_dir)
        return node

    return fill(cfg)


def _b(key, label, help_=""):
    return {"key": key, "label": label, "type": "bool", "help": help_}


# 表单结构：前端按此渲染。type: text / password / int / bool / select / list / intlist
SCHEMA = [
    {
        "title": "Telegram（必填）",
        "fields": [
            {"key": "telegram.bot_token", "label": "Bot Token", "type": "password", "required": True,
             "help": "在 @BotFather 创建机器人后获得，形如 123456:ABC-DEF..."},
            {"key": "telegram.owner_id", "label": "你的 Telegram 用户 ID", "type": "int", "required": True,
             "help": "可通过 @userinfobot 获取，纯数字"},
            {"key": "telegram.target_chat_id", "label": "目标超级群组 ID", "type": "int", "required": True,
             "help": "开启了「话题(Topics)」的超级群组，ID 以 -100 开头；机器人需为管理员并有管理话题权限"},
            {"key": "telegram.sudo_users_id", "label": "管理员用户 ID 列表", "type": "intlist",
             "help": "每行一个，通常填你自己的 ID 即可"},
            {"key": "telegram.api_url", "label": "自建 Bot API 地址（可选）", "type": "text",
             "help": "留空使用官方 API；自建可突破 50MB 文件限制"},
            _b("telegram.self_hosted_api", "使用自建 Bot API"),
        ],
    },
    {
        "title": "Telegram 行为",
        "fields": [
            {"key": "telegram.confirmation_type", "label": "发送成功确认方式", "type": "select",
             "options": [["emoji", "表情回应"], ["text", "文字消息"], ["none", "不确认"]]},
            _b("telegram.silent_confirmation", "确认消息静音发送"),
            _b("telegram.send_images_as_file", "图片以文件发送（保留原画质）"),
            _b("telegram.send_stickers_as_file", "贴纸以文件发送"),
            _b("telegram.skip_video_stickers", "跳过 Telegram 动态贴纸转换"),
            _b("telegram.skip_setting_commands", "不设置机器人命令列表"),
            _b("telegram.send_my_presence", "从 Telegram 发消息时显示 WhatsApp 在线"),
            _b("telegram.send_my_read_receipts", "从 Telegram 发消息时标记该会话已读"),
            _b("telegram.skip_startup_message", "不发送启动通知"),
            _b("telegram.spoiler_as_viewonce", "剧透(Spoiler)媒体以「阅后即焚」发送"),
            _b("telegram.reactions", "转发 WhatsApp 表情回应"),
            _b("telegram.tag_all_enabled", "允许 @all 提及群内所有人"),
            _b("telegram.auto_react_when_all_read", "所有人已读后自动回应"),
            {"key": "telegram.auto_react_remove_after_seconds", "label": "自动回应在 N 秒后移除（0=不移除）", "type": "int"},
        ],
    },
    {
        "title": "WhatsApp",
        "fields": [
            {"key": "whatsapp.session_name", "label": "会话名称", "type": "text",
             "help": "显示在手机「关联设备」列表里"},
            {"key": "whatsapp.client_mode", "label": "登录客户端类型", "type": "select",
             "options": [["android", "Android（推荐，可接收「阅后即焚」）"],
                         ["android_business", "Android - WhatsApp Business 账号"],
                         ["web", "桌面/网页客户端"]],
             "help": "仅在新配对时生效；若配对码登录失败可改为「桌面/网页客户端」再试"},
            {"key": "whatsapp.ignore_chats", "label": "忽略的会话", "type": "list",
             "help": "每行一个，填 @ 前面的部分（号码或群 ID），可用 /findcontacts、/getwagroups 命令查询"},
            {"key": "whatsapp.status_ignored_chats", "label": "不转发这些人的动态(Status)", "type": "list"},
            {"key": "whatsapp.tag_all_allowed_groups", "label": "允许 @all 的群", "type": "list"},
            _b("whatsapp.skip_documents", "不转发文件"),
            _b("whatsapp.skip_images", "不转发图片"),
            _b("whatsapp.skip_gifs", "不转发 GIF"),
            _b("whatsapp.skip_videos", "不转发视频"),
            _b("whatsapp.skip_voice_notes", "不转发语音"),
            _b("whatsapp.skip_audios", "不转发音频"),
            _b("whatsapp.skip_stickers", "不转发贴纸"),
            _b("whatsapp.skip_status", "不转发动态(Status)"),
            _b("whatsapp.skip_contacts", "不转发联系人名片"),
            _b("whatsapp.skip_locations", "不转发位置"),
            _b("whatsapp.skip_profile_picture_updates", "不转发头像变更"),
            _b("whatsapp.skip_group_settings_updates", "不转发群设置变更（进退群、改名等）"),
            _b("whatsapp.skip_chat_details", "不发送会话详情"),
            _b("whatsapp.skip_pinned_messages", "不同步置顶消息"),
            _b("whatsapp.send_revoked_message_updates", "转发撤回通知"),
            _b("whatsapp.send_edited_message_updates", "编辑后的消息作为新消息发送"),
            _b("whatsapp.send_my_messages_from_other_devices", "转发我在其他设备上发出的消息"),
            _b("whatsapp.create_thread_for_info_updates", "为资料变更创建话题"),
            _b("whatsapp.skip_offline_backlog", "跳过离线期间积压的消息"),
            {"key": "whatsapp.status_message_duration_seconds", "label": "WhatsApp 状态持续秒数", "type": "int"},
            {"key": "whatsapp.sticker_metadata.pack_name", "label": "贴纸包名", "type": "text"},
            {"key": "whatsapp.sticker_metadata.author_name", "label": "贴纸作者", "type": "text"},
        ],
    },
    {
        "title": "备份",
        "fields": [
            {"key": "backup.mode", "label": "数据库备份", "type": "select",
             "options": [["none", "关闭"], ["private", "私聊发给我"], ["thread", "发到群内锁定话题"]]},
            {"key": "backup.cron_schedule", "label": "备份时间（cron 表达式）", "type": "text",
             "help": "5 段式：分 时 日 月 周，例如 0 3 * * * 表示每天 03:00"},
            {"key": "backup.thread_name", "label": "备份话题名称", "type": "text"},
        ],
    },
    {
        "title": "通用",
        "fields": [
            {"key": "time_zone", "label": "时区", "type": "text", "help": "IANA 时区名，例如 Asia/Shanghai"},
            {"key": "time_format", "label": "时间格式（Go 格式）", "type": "text"},
            _b("debug_mode", "调试模式"),
            _b("whatsapp.whatsmeow_debug_mode", "whatsmeow 调试日志"),
        ],
    },
]


# ---------------------------------------------------------------- English translations
SECTION_EN = {
    "Telegram（必填）": "Telegram (required)",
    "Telegram 行为": "Telegram behaviour",
    "WhatsApp": "WhatsApp",
    "备份": "Backup",
    "通用": "General",
}

# key -> (label_en, help_en)
FIELD_EN = {
    "telegram.bot_token": ("Bot Token", "Get it from @BotFather, looks like 123456:ABC-DEF..."),
    "telegram.owner_id": ("Your Telegram user ID", "Numeric ID, get it from @userinfobot"),
    "telegram.target_chat_id": ("Target supergroup ID",
                                "A supergroup with Topics enabled, ID starts with -100; the bot must be an admin with 'Manage topics'"),
    "telegram.sudo_users_id": ("Admin user IDs", "One per line, usually just your own ID"),
    "telegram.api_url": ("Self-hosted Bot API URL (optional)", "Leave empty for the official API; self-hosting lifts the 50 MB file limit"),
    "telegram.self_hosted_api": ("Using a self-hosted Bot API", ""),
    "telegram.confirmation_type": ("Delivery confirmation", ""),
    "telegram.silent_confirmation": ("Send confirmations silently", ""),
    "telegram.send_images_as_file": ("Send images as files (original quality)", ""),
    "telegram.send_stickers_as_file": ("Send stickers as files", ""),
    "telegram.skip_video_stickers": ("Skip converting Telegram video stickers", ""),
    "telegram.skip_setting_commands": ("Don't register the bot command list", ""),
    "telegram.send_my_presence": ("Show me online on WhatsApp when sending from Telegram", ""),
    "telegram.send_my_read_receipts": ("Mark chat as read when sending from Telegram", ""),
    "telegram.skip_startup_message": ("Don't send a startup message", ""),
    "telegram.spoiler_as_viewonce": ("Send spoiler media as view-once", ""),
    "telegram.reactions": ("Forward WhatsApp reactions", ""),
    "telegram.tag_all_enabled": ("Allow @all to mention everyone in a group", ""),
    "telegram.auto_react_when_all_read": ("React automatically when everyone has read", ""),
    "telegram.auto_react_remove_after_seconds": ("Remove auto reaction after N seconds (0 = never)", ""),
    "whatsapp.session_name": ("Session name", "Shown in the phone's Linked devices list"),
    "whatsapp.client_mode": ("Client type used for linking",
                             "Only applies to new links; if pairing-code login fails, switch to Desktop/Web and retry"),
    "whatsapp.ignore_chats": ("Ignored chats",
                              "One per line, the part before @ (number or group ID); use /findcontacts and /getwagroups to look them up"),
    "whatsapp.status_ignored_chats": ("Don't forward statuses from these people", ""),
    "whatsapp.tag_all_allowed_groups": ("Groups allowed to use @all", ""),
    "whatsapp.skip_documents": ("Don't forward documents", ""),
    "whatsapp.skip_images": ("Don't forward images", ""),
    "whatsapp.skip_gifs": ("Don't forward GIFs", ""),
    "whatsapp.skip_videos": ("Don't forward videos", ""),
    "whatsapp.skip_voice_notes": ("Don't forward voice notes", ""),
    "whatsapp.skip_audios": ("Don't forward audio", ""),
    "whatsapp.skip_stickers": ("Don't forward stickers", ""),
    "whatsapp.skip_status": ("Don't forward statuses", ""),
    "whatsapp.skip_contacts": ("Don't forward contact cards", ""),
    "whatsapp.skip_locations": ("Don't forward locations", ""),
    "whatsapp.skip_profile_picture_updates": ("Don't forward profile picture changes", ""),
    "whatsapp.skip_group_settings_updates": ("Don't forward group changes (joins, leaves, renames…)", ""),
    "whatsapp.skip_chat_details": ("Don't send chat details", ""),
    "whatsapp.skip_pinned_messages": ("Don't sync pinned messages", ""),
    "whatsapp.send_revoked_message_updates": ("Forward 'message deleted' notices", ""),
    "whatsapp.send_edited_message_updates": ("Send edited messages as new messages", ""),
    "whatsapp.send_my_messages_from_other_devices": ("Forward messages I send from other devices", ""),
    "whatsapp.create_thread_for_info_updates": ("Create topics for profile/group info updates", ""),
    "whatsapp.skip_offline_backlog": ("Skip messages queued while offline", ""),
    "whatsapp.status_message_duration_seconds": ("WhatsApp status duration (seconds)", ""),
    "whatsapp.sticker_metadata.pack_name": ("Sticker pack name", ""),
    "whatsapp.sticker_metadata.author_name": ("Sticker author", ""),
    "backup.mode": ("Database backup", ""),
    "backup.cron_schedule": ("Backup schedule (cron)", "5 fields: min hour day month weekday, e.g. 0 3 * * * = every day at 03:00"),
    "backup.thread_name": ("Backup topic name", ""),
    "time_zone": ("Time zone", "IANA name, e.g. Asia/Shanghai"),
    "time_format": ("Time format (Go layout)", ""),
    "debug_mode": ("Debug mode", ""),
    "whatsapp.whatsmeow_debug_mode": ("whatsmeow debug logging", ""),
}

OPTION_EN = {
    "emoji": "Emoji reaction", "text": "Text message", "none": "None",
    "android": "Android (recommended, receives view-once media)",
    "android_business": "Android - WhatsApp Business account",
    "web": "Desktop / Web client",
    "private": "Send to me privately", "thread": "Locked topic in the group",
}
OPTION_EN_BACKUP_NONE = "Off"


def _apply_en():
    for sec in SCHEMA:
        sec["title_en"] = SECTION_EN.get(sec["title"], sec["title"])
        for f in sec["fields"]:
            label_en, help_en = FIELD_EN.get(f["key"], (f["label"], f.get("help", "")))
            f["label_en"] = label_en
            f["help_en"] = help_en
            if "options" in f:
                f["options"] = [
                    [val, zh, OPTION_EN_BACKUP_NONE if (f["key"] == "backup.mode" and val == "none") else OPTION_EN.get(val, zh)]
                    for val, zh, *_ in f["options"]
                ]


_apply_en()


def get_path(cfg: dict, dotted: str):
    node = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def set_path(cfg: dict, dotted: str, value):
    parts = dotted.split(".")
    node = cfg
    for part in parts[:-1]:
        if not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


FIELD_INDEX = {f["key"]: f for sec in SCHEMA for f in sec["fields"]}


def coerce(field: dict, value, lang: str = "zh"):
    t = field["type"]
    if t == "bool":
        return bool(value)
    if t in ("int", "intlist"):
        def to_int(x):
            try:
                return int(str(x).strip())
            except ValueError:
                raise ValueError(f"'{x}' is not a number" if lang == "en" else f"「{x}」不是数字") from None
    if t == "int":
        if value in (None, ""):
            return 0
        return to_int(value)
    if t in ("list", "intlist"):
        if isinstance(value, str):
            items = [x.strip() for x in value.replace(",", "\n").splitlines()]
        else:
            items = [str(x).strip() for x in (value or [])]
        items = [x for x in items if x]
        return [to_int(x) for x in items] if t == "intlist" else items
    if t == "select":
        allowed = [o[0] for o in field["options"]]
        if value not in allowed:
            raise ValueError(f"invalid option {value}" if lang == "en" else f"无效选项 {value}")
        return value
    return "" if value is None else str(value).strip()

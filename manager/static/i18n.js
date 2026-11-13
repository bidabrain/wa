'use strict';
// 界面文本中英对照。HTML 中用 data-i18n（文本）/ data-i18n-html（含标签）/ data-i18n-ph（placeholder）引用。
const I18N = {
  zh: {
    'app.title': 'WA-TG Bridge',
    'nav.overview': '概览', 'nav.android': '安卓手机', 'nav.login': 'WhatsApp 关联', 'nav.config': '转发配置',
    'nav.settings': '保活与提醒', 'nav.logs': '日志', 'nav.logout': '退出',

    'login.title': 'WA-TG Bridge 管理面板',
    'login.desc': '请输入管理密码（环境变量 <code>WEB_PASSWORD</code>，未设置时见容器日志或 <code>/data/.web_password</code>）。',
    'login.ph': '管理密码', 'login.btn': '登录', 'login.wrong': '密码错误',

    'state.RUNNING': '运行中', 'state.STARTING': '启动中', 'state.STOPPED': '已停止', 'state.STOPPING': '停止中',
    'state.BACKOFF': '启动失败重试中', 'state.FATAL': '启动失败', 'state.EXITED': '已退出', 'state.UNKNOWN': '未知',

    'ov.bridge': '转发服务', 'ov.autorun': '已启用自动运行', 'ov.manualStop': '已手动停止', 'ov.cfgMissing': '配置未完成：{x}',
    'ov.wa': 'WhatsApp 关联', 'ov.linked': '已关联', 'ov.unlinked': '未关联', 'ov.expired': '已失效',
    'ov.needLink': '需要在「WhatsApp 关联」页登录', 'ov.expiredSub': '关联已过期，请启动安卓后重新关联',
    'ov.android': '安卓模拟器', 'ov.booted': '已开机', 'ov.booting': '开机中…', 'ov.keepaliveRun': '自动保活运行中',
    'ov.canClose': '平时可以关闭', 'ov.noKvm': '⚠ 无 /dev/kvm，无法运行',
    'ov.lastOnline': '手机端最后在线', 'ov.never': '从未', 'ov.today': '今天', 'ov.daysAgo': '{n} 天前',
    'ov.openSoon': ' · 请尽快打开安卓同步',
    'ov.wizard': '设置向导',
    'ov.s1': '填写 Telegram 机器人与群组配置', 'ov.s1d': '在「转发配置」页填写 Bot Token、你的用户 ID、目标群 ID', 'ov.s1b': '去配置',
    'ov.s2': '启动安卓模拟器并安装 WhatsApp', 'ov.s2d': '一键下载安装官方 WhatsApp', 'ov.s2b': '去操作',
    'ov.s3': '在模拟器中注册/登录你的 WhatsApp', 'ov.s3d': '通过网页画面完成手机号验证', 'ov.s3b': '打开画面',
    'ov.s4': '把桥接关联为 WhatsApp 设备', 'ov.s4d': '使用配对码（推荐）或二维码', 'ov.s4b': '去关联',
    'ov.s5': '启动转发服务', 'ov.s5d': 'WhatsApp 消息开始转发到 Telegram 群组的话题中',
    'ov.s6': '关闭安卓模拟器（可选）', 'ov.s6d': '桥接独立运行，无需手机一直在线；记得定期开机保活', 'ov.s6b': '保活设置',
    'ov.expiryTitle': '关于关联设备有效期',
    'ov.expiryText': 'WhatsApp 规定：主手机超过约 14 天没有联网，所有关联设备（包括本桥接）会被自动注销。因此安卓模拟器平时可以关闭，但建议每隔一周左右打开一次，让手机端 WhatsApp 上线同步。你可以在「保活与提醒」中开启自动定期开机，或让机器人在 Telegram 里提醒你。<br><br>如果关联已经失效：安卓模拟器的数据是永久保存的，重新启动后 WhatsApp 仍是登录状态，直接在「WhatsApp 关联」页用配对码重新关联即可。',
    'btn.start': '启动', 'btn.stop': '停止', 'btn.restart': '重启', 'btn.shutdown': '关机', 'btn.cancel': '取消', 'btn.back': '返回',
    'btn.save': '保存', 'btn.refresh': '刷新', 'btn.send': '发送', 'msg.done': '已执行', 'msg.saved': '已保存',

    'an.title': '安卓模拟器', 'an.confirmStop': '确定关闭安卓模拟器？转发服务不受影响。', 'an.starting': '正在启动，首次开机需要 1–3 分钟',
    'an.stopped': '已关机',
    'an.noKvm': '容器内没有可用的 <code>/dev/kvm</code>，无法运行安卓模拟器。请确认宿主机开启了硬件虚拟化（Linux 上 <code>ls /dev/kvm</code> 存在），并用 <code>--device /dev/kvm</code> 启动容器。转发服务本身不需要 KVM，你也可以在「WhatsApp 关联」页使用二维码，用实体手机扫码。',
    'an.app': 'WhatsApp 应用', 'an.appNeedBoot': '启动模拟器后可安装/更新。', 'an.appNotInstalled': 'WhatsApp 尚未安装',
    'an.appInstalled': '✓ 已安装 WhatsApp {v}', 'an.appUpdated': '更新于 {d}',
    'an.install': '下载并安装官方 WhatsApp', 'an.update': '检查并更新到最新版', 'an.reinstall': '强制重新下载安装',
    'an.upload': '上传 APK', 'an.uploading': '正在上传…', 'an.uploaded': '上传完成，正在安装', 'an.jobStarted': '任务已开始',
    'an.updateNote': '更新使用覆盖安装，WhatsApp 的聊天和登录状态都会保留。如果官方网站下载失败，也可以自己下载新版官方 APK 后点「上传 APK」升级。',
    'an.first': '首次使用',
    'an.f1': '启动模拟器，等待开机完成（首次约 1–3 分钟）。',
    'an.f2': '点击上方按钮安装 WhatsApp（自动从 whatsapp.com 下载官方 APK）。',
    'an.f3': '在右侧画面中打开 WhatsApp，用你的手机号注册登录，输入短信/电话验证码。',
    'an.f4': '到「WhatsApp 关联」页面把桥接作为关联设备登录。',
    'an.primaryWarn': '注意：WhatsApp 一个号码只能有一台「主手机」。在模拟器上注册后，原手机上的 WhatsApp 会退出；原手机可以之后通过「关联为配套设备」继续使用。',
    'an.quick': '快捷操作', 'an.home': '主屏幕', 'an.back': '返回', 'an.recent': '多任务', 'an.wake': '唤醒屏幕',
    'an.openWa': '打开 WhatsApp', 'an.textTitle': '向模拟器输入文字（英文/数字）', 'an.textPh': '例如验证码', 'an.textSent': '已发送',
    'an.screen': '屏幕',
    'an.screenTip': '用鼠标点击/拖动操作手机，键盘可直接输入。画面不显示时点「重新连接」。',
    'an.reconnect': '重新连接', 'an.newWindow': '新窗口打开',
    'an.notRunning': '安卓模拟器未运行<br><br>到「安卓手机」页点击「启动」',
    'an.androidScreen': '安卓屏幕',

    'wa.linkedTitle': '已关联 ✓', 'wa.account': '账号：',
    'wa.linkedDesc': '桥接已作为关联设备登录。现在可以关闭安卓模拟器，转发会继续工作。',
    'wa.logout': '注销关联', 'wa.localOnly': '仅清除本地会话',
    'wa.logoutTip': '「注销关联」会同时从手机的关联设备列表中移除；若手机端已手动移除，用「仅清除本地会话」。',
    'wa.confirmLogout': '确定注销？转发会停止，需要重新关联。', 'wa.confirmLocal': '确定清除本地会话？',
    'wa.loggedOut': '已注销', 'wa.cleared': '已清除',
    'wa.title': '把桥接关联到你的 WhatsApp',
    'wa.expired': '之前的关联已失效（主手机离线过久或在手机上被移除）。安卓模拟器中的 WhatsApp 数据仍然保留：启动安卓后，用下面的配对码重新关联即可。',
    'wa.needBoot': '安卓模拟器未开机。配对码方式需要在模拟器的 WhatsApp 里操作，请先到「安卓手机」页启动。',
    'wa.startAndroid': '启动安卓模拟器',
    'wa.modeCode': '配对码（推荐，在模拟器内输入 8 位码）',
    'wa.phonePh': 'WhatsApp 手机号，含国家码，如 8613800000000',
    'wa.modeQr': '二维码（用另一台实体手机扫码）',
    'wa.qrNote': '模拟器没有摄像头，无法扫码；在模拟器里重新授权请使用配对码，效果与扫码相同。',
    'wa.start': '开始关联', 'wa.pauseNote': '关联过程中转发服务会暂停，成功后自动启动。',
    'wa.pairTitle': '关联 WhatsApp', 'wa.connecting': '正在连接 WhatsApp 服务器…', 'wa.code': '配对码：',
    'wa.c1': '在右侧模拟器中打开 WhatsApp（通常会直接弹出「输入代码以关联新设备」通知，点击它）。',
    'wa.c2': '或手动进入：右上角 ⋮ → 已关联的设备 → 关联新设备 → 改用电话号码关联。',
    'wa.c3': '输入上面的 8 位配对码（大小写不敏感，不需要输入横线）。',
    'wa.qrLeft': '剩余 {n} 秒自动刷新',
    'wa.q1': '在主手机 WhatsApp 中：⋮ → 已关联的设备 → 关联新设备。', 'wa.q2': '扫描上面的二维码。',
    'wa.finishing': '✓ 手机已确认，正在完成登录…',
    'wa.success': '🎉 关联成功！{jid}', 'wa.successDesc': '转发服务已自动启动。现在可以关闭安卓模拟器。',
    'wa.errHint': '如果配对码一直失败，可在「转发配置 → WhatsApp → 登录客户端类型」改为「桌面/网页客户端」后重试。',

    'cfg.title': 'watgbridge 转发配置', 'cfg.raw': '高级：直接编辑 YAML', 'cfg.form': '返回表单',
    'cfg.prep': '准备工作：① 在 @BotFather 创建机器人；② 新建一个 Telegram 超级群组并开启「话题(Topics)」；③ 把机器人拉进群并设为管理员（需要「管理话题」权限）；④ 群 ID 可以把群里任一消息转发给 @userinfobot / @getidsbot 获得；⑤ 先私聊机器人发送 /start。',
    'cfg.saveRestart': '保存并重启转发', 'cfg.saveOnly': '仅保存', 'cfg.saveYaml': '保存 YAML',
    'cfg.yamlNote': '保存后需重启转发生效。SQLite 数据库路径会被固定到 /data/bridge。', 'cfg.bridgeStarted': '已启动转发',

    'set.kaTitle': '自动保活',
    'set.kaDesc': '当手机端离线超过设定天数时，自动启动安卓模拟器并打开 WhatsApp，运行一段时间后自动关机。需要容器有 /dev/kvm。',
    'set.kaEnable': '开启自动保活', 'set.kaDays': '每隔多少天开机一次', 'set.kaDaysHelp': '建议 5–10 天，必须小于 14 天',
    'set.kaMinutes': '每次运行多少分钟', 'set.kaMinutesHelp': '通常 15–30 分钟足够同步',
    'set.kaUpdate': '保活开机时自动检查并更新 WhatsApp 到官方最新版',
    'set.rmTitle': 'Telegram 提醒', 'set.rmEnable': '手机端长时间离线或关联失效时，通过机器人私聊提醒我',
    'set.rmDays': '离线超过多少天提醒', 'set.rmDaysHelp': '每天最多提醒一次', 'set.test': '发送测试提醒',
    'set.testSent': '已发送，请查看 Telegram',
    'set.langNote': '提醒消息使用当前界面语言。',

    'log.bridge': '转发 (watgbridge)', 'log.pair': 'WhatsApp 配对', 'log.emulator': '安卓模拟器', 'log.manager': '管理面板',
    'log.auto': '自动刷新', 'log.empty': '（暂无日志）', 'log.update': '版本更新',

    'nav.update': '版本更新',
    'up.title': 'watgbridge 版本', 'up.desc': '无需重建 Docker 镜像即可更新转发程序。新版本保存在 /data/bin，重建容器也不会丢失；更新后若启动失败会自动回滚。',
    'up.current': '当前使用', 'up.builtin': '镜像内置', 'up.prev': '上一版本（可回滚）', 'up.none': '无',
    'up.src.image': '镜像内置', 'up.src.release': '预编译 Release', 'up.src.source': '源码编译', 'up.src.upload': '手动上传',
    'up.installedAt': '安装于 {d}', 'up.rollback': '回滚到上一版本', 'up.confirmRollback': '确定回滚到上一版本？',
    'up.relTitle': '方式一：下载官方预编译版本（最快）',
    'up.relDesc': '从 GitHub Release 下载 watgbridge 官方发布的 Linux 二进制文件。',
    'up.relBtn': '更新到所选版本', 'up.relLatest': '（最新）', 'up.relLoading': '加载中…', 'up.relFail': '无法获取版本列表',
    'up.relNote': '预编译版本只替换转发程序，WhatsApp 配对工具保持当前版本。如果以后重新关联时提示数据库版本错误，请用「方式二：从源码编译」，它会同时编译配对工具。',
    'up.srcTitle': '方式二：从源码编译（推荐用于跨大版本更新）',
    'up.srcDesc': '在容器内拉取 watgbridge 源码，同时编译转发程序和配对工具，保证两者使用同一版本。可填写分支、标签或提交，首次编译需下载依赖，约需几分钟和 1–2 GB 内存。',
    'up.srcPh': '分支 / 标签 / 提交，如 main、v1.13.13', 'up.srcBtn': '开始编译并更新',
    'up.upTitle': '方式三：上传二进制文件', 'up.upDesc': '上传你自己编译好的 Linux watgbridge 可执行文件。', 'up.upBtn': '选择文件上传',
    'up.apkTitle': 'WhatsApp 安卓客户端', 'up.apkDesc': '模拟器中的 WhatsApp 在「安卓手机」页面检查更新（覆盖安装，不会丢失登录）；也可在「保活与提醒」中开启保活时自动更新。',
    'up.apkGo': '前往安卓手机页面', 'up.started': '已开始，请稍候', 'up.confirm': '更新期间转发会短暂中断，继续？',
  },
  en: {
    'app.title': 'WA-TG Bridge',
    'nav.overview': 'Overview', 'nav.android': 'Android', 'nav.login': 'WhatsApp link', 'nav.config': 'Bridge config',
    'nav.settings': 'Keep-alive', 'nav.logs': 'Logs', 'nav.logout': 'Log out',

    'login.title': 'WA-TG Bridge manager',
    'login.desc': 'Enter the admin password (env var <code>WEB_PASSWORD</code>; if unset, see the container log or <code>/data/.web_password</code>).',
    'login.ph': 'Admin password', 'login.btn': 'Log in', 'login.wrong': 'Wrong password',

    'state.RUNNING': 'Running', 'state.STARTING': 'Starting', 'state.STOPPED': 'Stopped', 'state.STOPPING': 'Stopping',
    'state.BACKOFF': 'Failed, retrying', 'state.FATAL': 'Failed to start', 'state.EXITED': 'Exited', 'state.UNKNOWN': 'Unknown',

    'ov.bridge': 'Bridge', 'ov.autorun': 'Auto-start enabled', 'ov.manualStop': 'Stopped manually', 'ov.cfgMissing': 'Config incomplete: {x}',
    'ov.wa': 'WhatsApp link', 'ov.linked': 'Linked', 'ov.unlinked': 'Not linked', 'ov.expired': 'Expired',
    'ov.needLink': 'Link it on the "WhatsApp link" page', 'ov.expiredSub': 'The link expired; start Android and link again',
    'ov.android': 'Android emulator', 'ov.booted': 'Booted', 'ov.booting': 'Booting…', 'ov.keepaliveRun': 'Keep-alive run in progress',
    'ov.canClose': 'Can stay off most of the time', 'ov.noKvm': '⚠ No /dev/kvm, cannot run',
    'ov.lastOnline': 'Phone last online', 'ov.never': 'Never', 'ov.today': 'Today', 'ov.daysAgo': '{n} days ago',
    'ov.openSoon': ' · please start Android soon',
    'ov.wizard': 'Setup guide',
    'ov.s1': 'Fill in the Telegram bot and group settings', 'ov.s1d': 'Bot Token, your user ID and target group ID on the "Bridge config" page', 'ov.s1b': 'Configure',
    'ov.s2': 'Start the Android emulator and install WhatsApp', 'ov.s2d': 'One-click install of the official WhatsApp', 'ov.s2b': 'Open',
    'ov.s3': 'Register / log in to WhatsApp in the emulator', 'ov.s3d': 'Verify your phone number through the web screen', 'ov.s3b': 'Show screen',
    'ov.s4': 'Link the bridge as a WhatsApp device', 'ov.s4d': 'Using a pairing code (recommended) or QR code', 'ov.s4b': 'Link',
    'ov.s5': 'Start the bridge', 'ov.s5d': 'WhatsApp messages are forwarded to topics in your Telegram group',
    'ov.s6': 'Shut down the emulator (optional)', 'ov.s6d': 'The bridge runs on its own; just boot the phone regularly to keep the link alive', 'ov.s6b': 'Keep-alive',
    'ov.expiryTitle': 'About linked device expiry',
    'ov.expiryText': 'WhatsApp logs out all linked devices (including this bridge) when the primary phone has been offline for about 14 days. So the emulator can stay off most of the time, but start it about once a week so WhatsApp on the phone can sync. You can enable automatic periodic boots or Telegram reminders under "Keep-alive".<br><br>If the link has already expired: the emulator\'s data is kept permanently, so after starting it WhatsApp is still logged in — just link again with a pairing code on the "WhatsApp link" page.',
    'btn.start': 'Start', 'btn.stop': 'Stop', 'btn.restart': 'Restart', 'btn.shutdown': 'Shut down', 'btn.cancel': 'Cancel', 'btn.back': 'Back',
    'btn.save': 'Save', 'btn.refresh': 'Refresh', 'btn.send': 'Send', 'msg.done': 'Done', 'msg.saved': 'Saved',

    'an.title': 'Android emulator', 'an.confirmStop': 'Shut down the Android emulator? The bridge keeps running.', 'an.starting': 'Starting; the first boot takes 1–3 minutes',
    'an.stopped': 'Shut down',
    'an.noKvm': '<code>/dev/kvm</code> is not available in the container, so the Android emulator cannot run. Make sure hardware virtualization is enabled on the host (<code>ls /dev/kvm</code> exists on Linux) and start the container with <code>--device /dev/kvm</code>. The bridge itself does not need KVM; you can also use a QR code with a physical phone on the "WhatsApp link" page.',
    'an.app': 'WhatsApp app', 'an.appNeedBoot': 'Start the emulator to install or update.', 'an.appNotInstalled': 'WhatsApp is not installed',
    'an.appInstalled': '✓ WhatsApp {v} installed', 'an.appUpdated': 'updated {d}',
    'an.install': 'Download & install official WhatsApp', 'an.update': 'Check for updates', 'an.reinstall': 'Force re-download & install',
    'an.upload': 'Upload APK', 'an.uploading': 'Uploading…', 'an.uploaded': 'Uploaded, installing', 'an.jobStarted': 'Task started',
    'an.updateNote': 'Updates install over the existing app, so chats and the login are kept. If downloading from whatsapp.com fails, download a newer official APK yourself and use "Upload APK".',
    'an.first': 'First-time setup',
    'an.f1': 'Start the emulator and wait for it to boot (1–3 minutes the first time).',
    'an.f2': 'Click the button above to install WhatsApp (official APK from whatsapp.com).',
    'an.f3': 'Open WhatsApp on the screen at the right, register with your number and enter the SMS/call code.',
    'an.f4': 'Go to "WhatsApp link" and link the bridge as a device.',
    'an.primaryWarn': 'Note: a WhatsApp number can only have one primary phone. After registering in the emulator, WhatsApp on your old phone is logged out; you can later re-add that phone as a companion device.',
    'an.quick': 'Quick actions', 'an.home': 'Home', 'an.back': 'Back', 'an.recent': 'Recents', 'an.wake': 'Wake screen',
    'an.openWa': 'Open WhatsApp', 'an.textTitle': 'Type text into the emulator (ASCII)', 'an.textPh': 'e.g. a verification code', 'an.textSent': 'Sent',
    'an.screen': 'Screen',
    'an.screenTip': 'Click/drag with the mouse; the keyboard types directly. Use "Reconnect" if the screen is blank.',
    'an.reconnect': 'Reconnect', 'an.newWindow': 'Open in new window',
    'an.notRunning': 'The Android emulator is not running<br><br>Start it on the "Android" page',
    'an.androidScreen': 'Android screen',

    'wa.linkedTitle': 'Linked ✓', 'wa.account': 'Account: ',
    'wa.linkedDesc': 'The bridge is logged in as a linked device. You can shut down the emulator now; forwarding keeps working.',
    'wa.logout': 'Log out link', 'wa.localOnly': 'Clear local session only',
    'wa.logoutTip': '"Log out link" also removes it from the phone\'s Linked devices list; if you already removed it on the phone, use "Clear local session only".',
    'wa.confirmLogout': 'Log out? Forwarding stops and you will need to link again.', 'wa.confirmLocal': 'Clear the local session?',
    'wa.loggedOut': 'Logged out', 'wa.cleared': 'Cleared',
    'wa.title': 'Link the bridge to your WhatsApp',
    'wa.expired': 'The previous link has expired (primary phone offline too long, or removed on the phone). WhatsApp data in the emulator is still there: start Android and link again with a pairing code below.',
    'wa.needBoot': 'The Android emulator is not running. The pairing-code method needs WhatsApp in the emulator, so start it on the "Android" page first.',
    'wa.startAndroid': 'Start Android emulator',
    'wa.modeCode': 'Pairing code (recommended; enter an 8-character code in the emulator)',
    'wa.phonePh': 'WhatsApp phone number with country code, e.g. 14155550123',
    'wa.modeQr': 'QR code (scan with another physical phone)',
    'wa.qrNote': 'The emulator has no camera and cannot scan QR codes; to re-authorize from the emulator use a pairing code, which works the same way.',
    'wa.start': 'Start linking', 'wa.pauseNote': 'The bridge pauses while linking and restarts automatically on success.',
    'wa.pairTitle': 'Link WhatsApp', 'wa.connecting': 'Connecting to WhatsApp…', 'wa.code': 'Pairing code:',
    'wa.c1': 'Open WhatsApp in the emulator on the right (a "Enter code to link new device" notification usually pops up — tap it).',
    'wa.c2': 'Or go manually: ⋮ (top right) → Linked devices → Link a device → Link with phone number instead.',
    'wa.c3': 'Enter the 8-character code above (not case-sensitive, no dash needed).',
    'wa.qrLeft': 'Refreshes in {n} s',
    'wa.q1': 'On the primary phone: WhatsApp ⋮ → Linked devices → Link a device.', 'wa.q2': 'Scan the QR code above.',
    'wa.finishing': '✓ Confirmed on the phone, finishing login…',
    'wa.success': '🎉 Linked! {jid}', 'wa.successDesc': 'The bridge has started. You can shut down the emulator now.',
    'wa.errHint': 'If pairing codes keep failing, set "Bridge config → WhatsApp → Client type used for linking" to "Desktop / Web client" and try again.',

    'cfg.title': 'watgbridge configuration', 'cfg.raw': 'Advanced: edit YAML', 'cfg.form': 'Back to form',
    'cfg.prep': 'Before you start: ① create a bot with @BotFather; ② create a Telegram supergroup and enable Topics; ③ add the bot to the group as an admin with "Manage topics"; ④ get the group ID by forwarding any group message to @userinfobot / @getidsbot; ⑤ send /start to your bot in a private chat.',
    'cfg.saveRestart': 'Save & restart bridge', 'cfg.saveOnly': 'Save only', 'cfg.saveYaml': 'Save YAML',
    'cfg.yamlNote': 'Restart the bridge to apply. SQLite database paths are pinned to /data/bridge.', 'cfg.bridgeStarted': 'Bridge started',

    'set.kaTitle': 'Automatic keep-alive',
    'set.kaDesc': 'When the phone has been offline for the set number of days, automatically start the emulator, open WhatsApp, and shut it down after a while. Requires /dev/kvm.',
    'set.kaEnable': 'Enable automatic keep-alive', 'set.kaDays': 'Boot every N days', 'set.kaDaysHelp': '5–10 days recommended; must be under 14',
    'set.kaMinutes': 'Run for N minutes', 'set.kaMinutesHelp': '15–30 minutes is usually enough to sync',
    'set.kaUpdate': 'Check for and install the latest official WhatsApp during keep-alive boots',
    'set.rmTitle': 'Telegram reminders', 'set.rmEnable': 'Message me via the bot when the phone is offline too long or the link expires',
    'set.rmDays': 'Remind after N days offline', 'set.rmDaysHelp': 'At most once a day', 'set.test': 'Send test reminder',
    'set.testSent': 'Sent, check Telegram',
    'set.langNote': 'Reminders use the current interface language.',

    'log.bridge': 'Bridge (watgbridge)', 'log.pair': 'WhatsApp pairing', 'log.emulator': 'Android emulator', 'log.manager': 'Manager',
    'log.auto': 'Auto refresh', 'log.empty': '(no logs yet)', 'log.update': 'Updates',

    'nav.update': 'Updates',
    'up.title': 'watgbridge version', 'up.desc': 'Update the bridge without rebuilding the Docker image. New versions are stored in /data/bin and survive container re-creation; if a new version fails to start it is rolled back automatically.',
    'up.current': 'In use', 'up.builtin': 'Built into image', 'up.prev': 'Previous version (rollback)', 'up.none': 'None',
    'up.src.image': 'Image built-in', 'up.src.release': 'Prebuilt release', 'up.src.source': 'Built from source', 'up.src.upload': 'Uploaded',
    'up.installedAt': 'installed {d}', 'up.rollback': 'Roll back', 'up.confirmRollback': 'Roll back to the previous version?',
    'up.relTitle': 'Option 1: download an official prebuilt release (fastest)',
    'up.relDesc': 'Downloads the official Linux binary from watgbridge GitHub Releases.',
    'up.relBtn': 'Update to selected version', 'up.relLatest': ' (latest)', 'up.relLoading': 'Loading…', 'up.relFail': 'Could not load releases',
    'up.relNote': 'Prebuilt releases only replace the bridge; the WhatsApp pairing tool stays at its current version. If re-linking later reports a database version error, use "Option 2: build from source", which also rebuilds the pairing tool.',
    'up.srcTitle': 'Option 2: build from source (recommended for big version jumps)',
    'up.srcDesc': 'Fetches watgbridge source inside the container and builds both the bridge and the pairing tool so they always match. Accepts a branch, tag or commit. The first build downloads dependencies and needs a few minutes and 1–2 GB RAM.',
    'up.srcPh': 'branch / tag / commit, e.g. main, v1.13.13', 'up.srcBtn': 'Build & update',
    'up.upTitle': 'Option 3: upload a binary', 'up.upDesc': 'Upload a Linux watgbridge executable you built yourself.', 'up.upBtn': 'Choose file',
    'up.apkTitle': 'WhatsApp Android app', 'up.apkDesc': 'Check for WhatsApp updates on the "Android" page (installs over the existing app, the login is kept), or enable auto-update during keep-alive boots.',
    'up.apkGo': 'Go to Android page', 'up.started': 'Started, please wait', 'up.confirm': 'Forwarding pauses briefly during the update. Continue?',
  },
};

function detectLang() {
  let saved = null;
  try { saved = localStorage.getItem('lang'); } catch (e) { /* ignore */ }
  if (saved === 'zh' || saved === 'en') return saved;
  return (navigator.language || 'zh').toLowerCase().startsWith('zh') ? 'zh' : 'en';
}

let LANG = detectLang();

function T(key, vars) {
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.zh[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

// 后端返回的双语对象 {zh, en} 或普通字符串
function loc(x) {
  if (x && typeof x === 'object') return x[LANG] || x.zh || '';
  return x ?? '';
}

function applyI18n(root = document) {
  document.documentElement.lang = LANG === 'en' ? 'en' : 'zh-CN';
  root.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = T(el.dataset.i18n); });
  root.querySelectorAll('[data-i18n-html]').forEach((el) => { el.innerHTML = T(el.dataset.i18nHtml); });
  root.querySelectorAll('[data-i18n-ph]').forEach((el) => { el.placeholder = T(el.dataset.i18nPh); });
}

function setLang(lang) {
  LANG = lang === 'en' ? 'en' : 'zh';
  try { localStorage.setItem('lang', LANG); } catch (e) { /* ignore */ }
  document.cookie = `lang=${LANG}; path=/; max-age=31536000; samesite=lax`;
  applyI18n();
}

function langSwitcherHtml() {
  return `<select id="langSel" class="lang-sel" aria-label="Language">
    <option value="zh" ${LANG === 'zh' ? 'selected' : ''}>中文</option>
    <option value="en" ${LANG === 'en' ? 'selected' : ''}>English</option></select>`;
}

document.cookie = `lang=${LANG}; path=/; max-age=31536000; samesite=lax`;

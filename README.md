# 河海课表 PWA

打开就是一个周课表：数据从河海大学教务系统抓取后加密推送，没网也能看。

**两种用法**：

| 方式 | 入口 | 特点 |
| --- | --- | --- |
| **安卓 App（推荐）** | [下载 hhu-schedule.apk](https://github.com/Boccaccio-0/hhu-schedule/releases/download/apk/hhu-schedule.apk) | 真·安装包，桌面图标、启动快、离线可用；联网时自动拉最新课表 |
| 网页版 / PWA | <https://boccaccio-0.github.io/hhu-schedule/> | 免安装，iPhone/电脑也能用；Chrome 里可「添加到主屏幕」 |

## 安装安卓 App

1. 手机浏览器打开下载链接：<https://github.com/Boccaccio-0/hhu-schedule/releases/download/apk/hhu-schedule.apk>（约 0.5 MB）；
2. 下载完成后点开安装，系统会提示「**出于安全考虑，禁止安装未知应用**」——按提示允许一次（小米/华为/OPPO/vivo 一般在弹窗里的设置页打开开关，或到「设置 → 应用 → 特殊权限 → 安装未知应用」给浏览器授权）；
3. 装好后桌面出现「课表」图标，打开输入口令即可。

**手机更新**：从 1.2 起，在「设置 → 检查应用更新」查看新版（解锁页也有入口）。发现新版后点「下载更新」，浏览器下载完成后，点开 APK 按 Android 提示安装；系统仍需要你确认安装。无网络或检查失败时可重试，或打开下载页手动下载。网页 / PWA 不显示 Android 更新入口。

**首次迁移**：1.0 / 1.1 使用临时签名，升级到 1.2 需卸载旧版后再安装；卸载会清除本机修改，请先记录自定义安排。1.2 起使用固定签名，以后可覆盖安装并保留时间安排与口令。

日常课表变化不需要安装新版本：App 打开时会自动同步；无法联网时仍可查看已有课表和时间安排。

## 它长什么样

- 首屏是周一~周日 × 五个大节的课表网格，顶栏显示「第 X 周」和日期区间，左右箭头切周
- 点课程格子弹出详情：教师、教室、节次时间、周次范围、课程群号
- 非本周的课程灰显（虚线框），无固定时间的课程（如实习、实践课）列在课表下方
- 「现在是第几周」由教务系统教学周历自动推算，也可以在设置里手动微调

## 每日时间安排

解锁后可在顶部切换「课表 / 时间安排」。时间安排内置《考研四科每日时间计划.xlsx》的 22 个每日时段、四科学习汇总和备注；课表仍保持只读。

- 进入「时间安排」会按当前设备的本地时间自动定位，并高亮正在进行的时段。空档时定位下一段，当天结束后定位最后一段；重叠时标出所有当前时段并定位开始最早的一段。时间标记每分钟更新，后台同步、保存编辑和分钟变化不会主动滚动页面。
- 点击「新增时段」或每条安排的「编辑 / 删除」管理计划。可以修改起止时间、安排类别和具体任务；结束时间支持 `24:00`，跨午夜请拆成两段。
- 时长和每日汇总自动重算。重叠时段会提示但允许保存，汇总会分别累计各条时长；学习日跨度包含首末学习时段之间的休息。
- 修改只保存在当前浏览器或安卓 App 中，不自动同步到其他设备，也不写回原 Excel。刷新、重新打开和课表同步不会覆盖修改。
- 「恢复原始安排」会在确认后替换本机计划；设置中的「清除本机数据」也会清除计划修改。清除浏览器数据或卸载 App 可能导致修改丢失。
- 缓存无法读取时会保留原数据并停用编辑，可重试或主动恢复默认。保存失败时会显示错误，编辑内容保留供重试。

网页版更新后可使用；安卓功能更新需重新构建并安装包含最新 `web/` 的 APK。

## 工作原理

```text
你的电脑（国内网络）
   └─ 每天 19:00 计划任务跑 local_update.py
      ├─ 登录统一身份认证（curl_cffi 模拟 Chrome 指纹）
      ├─ 解析「学期理论课表」+「教学周历」
      ├─ 用口令加密成 web/data/schedule.enc.json
      └─ 提交推送到 GitHub（git 端口被墙时自动改走 API）

GitHub Actions
   └─ 收到推送后自动部署到 GitHub Pages

手机 Chrome
   └─ 输入一次口令 → WebCrypto 解密 → 存本机 → 离线可用
```

### 为什么抓取放在本机，而不是 GitHub Actions？

实测结论：学校教务系统的 WAF **按 IP 拦截数据中心 / 境外来源**。从 GitHub Actions 的机器访问：

| 目标 | 结果 |
| --- | --- |
| `authserver.hhu.edu.cn`（登录页） | 200（纯 curl 可以，Chrome 指纹客户端连接被重置） |
| `jwxt.hhu.edu.cn`（教务系统） | **483（拦截码，任何客户端、任何 TLS 指纹都被拦）** |
| `www.hhu.edu.cn`（学校官网） | 200 |

这不是代码能绕过的限制，云端定时抓取不可行。因此改成：**本机抓取（国内网络，实测完全正常）→ 推送到 GitHub → 云端自动部署**。手机上依然是全自动的。

## 已经配置好的部分

| 项目 | 位置 |
| --- | --- |
| 线上课表 | <https://boccaccio-0.github.io/hhu-schedule/> |
| 解锁口令 | 保存在 `scripts/local_secrets.json`（不上传），手机上输一次即可 |
| 自动同步 | Windows 计划任务「HHU课表自动同步」，每天 19:00，电脑关机错过会自动补跑 |

## 日常使用

| 情况 | 做法 |
| --- | --- |
| 什么都不做 | 每天自动同步一次；调课当天可手动同步 |
| 想立刻更新 | 双击 `scripts/local_update.bat` |
| 教务系统改了密码 | 改 `scripts/local_secrets.json` 里的 `password` |
| 换手机 / 重装 | 用同一个口令解锁即可 |
| 换口令 | 改 `local_secrets.json` 里的 `passphrase` → 手动同步一次 → 手机上点「重新输入口令」 |

网页版安装到桌面（安卓 Chrome）：打开线上地址 → 输入口令 → 右上角 ⋮ → 「安装应用 / 添加到主屏幕」；iPhone 用 Safari 打开 → 分享 → 「添加到主屏幕」。

## 常见问题

- **`local_update.bat` 提示 git push 失败**：国内访问 `github.com:443` 经常被重置。脚本会自动改用 GitHub API 推送（`scripts/api_push.py`），一般能成功；仍失败就过一会儿再双击一次，数据不会丢。
- **计划任务没跑**：确认当时电脑是开机状态；被错过的任务 Windows 会在开机后自动补跑。也可以直接双击 `local_update.bat` 手动同步。
- **同步日志天天写「课表数据没有变化」，但 GitHub 上迟迟没有新提交**：先确认本机能不能解析 GitHub 域名——
  ```powershell
  Resolve-DnsName github.com      # 应返回真实 IP；若是 0.0.0.0，说明被 hosts 屏蔽了
  ```
  某些游戏模组工具会往 `C:\Windows\System32\drivers\etc\hosts` 写 `0.0.0.0 github.com / api.github.com / codeload.github.com` 来阻止自己自动更新（实测 **XXMI Launcher** 会这么干，并留下 `# XXMI Launcher auto-update block` 注释），这会把本项目的 **git push 与 API 推送两条通道一起掐断**。用管理员权限打开 hosts，把那几行注释掉，再执行 `ipconfig /flushdns` 即可恢复。想立刻确认推送通道是否通畅，可以跑 `git push --dry-run origin main`，输出 `Everything up-to-date` 就说明通。
- **手机提示「口令不对」**：输入的口令要和 `scripts/local_secrets.json` 里的 `passphrase` 一致。
- **「现在是第几周」不对**：进设置用「起始前移一周 / 后移一周」校正，或核对教务系统教学周历后「恢复自动日期」。
- **教务系统改版导致抓取失败**：`python tests/test_parse.py` 会先报错，按新页面结构更新 `scripts/hhu/parse.py` 即可；该测试也会在 GitHub 部署前自动运行。
- **某天之后不再自动更新**：GitHub 对公开仓库有「连续 60 天无仓库活动即停用**定时**工作流」的策略；本项目两个工作流都由 push 触发，通常不受该策略影响。若真收到停用邮件，到 Actions 页面点 *Enable workflow* 即可；本机计划任务不受影响。

## 换一台电脑重新搭建

1. 安装 Python 3.12 与 Git；
2. `pip install -r scripts/requirements.txt`；
3. `git clone https://github.com/Boccaccio-0/hhu-schedule.git`；
4. 复制 `scripts/local_secrets.example.json` 为 `scripts/local_secrets.json`，填学号、密码、口令；
5. 双击 `scripts/install_task.bat` 注册每日计划任务（可选）；
6. 仓库 **Settings → Pages → Source** 需为 **GitHub Actions**（已配置）。

## 隐私说明

- 仓库是公开的，但 `web/data/schedule.enc.json` 用 **AES-256-GCM** 加密，密钥由口令经 PBKDF2-SHA256（20 万次迭代）派生，没有口令无法还原内容。
- 学号、密码、口令只存在于本机 `scripts/local_secrets.json`（已被 `.gitignore` 忽略），不进入仓库、不上传 GitHub。
- 网页把口令存在手机浏览器的 localStorage 里，仅用于解密；设置里「清除本机数据」可全部删掉。
- 仓库里的测试样本是**脱敏**过的（课程名、教师、教室、学号都换成了虚构值）。
- 不再需要本机 git 凭据时，可在「Windows 凭据管理器 → 普通凭据 → git:https://github.com」里删除。

## 本地开发与测试

### 安卓构建与发布

- Actions 从仓库 Secrets 读取 `ANDROID_KEYSTORE_BASE64`（固定 PKCS12 密钥库）及 `ANDROID_KEYSTORE_PASSWORD`，别名为 `hhu-release`。缺少密钥时构建失败，不再使用随机调试签名。
- 密钥及密码必须单独备份，不提交到 Git。更换或丢失密钥会导致已安装版本无法覆盖升级。
- 每次发布功能更新，递增 `android/app/build.gradle` 的 `versionCode` 并更新 `versionName`。课表内容同步无需提升应用版本。
- 工作流先运行版本解析单元测试，再构建签名 APK；从实际产物生成 `update.json`，先上传 APK 再上传版本信息。更新检查读取 GitHub Release 附件，不需要登录或 API Token，也不上传本机计划。
- 本地使用 JDK 17、Gradle 8.7、Android SDK 34。在 `android/` 运行 `gradle testDebugUnitTest` 测试；构建 release 还需设置 `ANDROID_KEYSTORE_PATH` 和 `ANDROID_KEYSTORE_PASSWORD`，并先将 `web/` 复制到 `android/app/src/main/assets/www/`。

### 网页与课表测试

```bash
pip install -r scripts/requirements.txt

python tests/test_parse.py        # 解析回归测试（用脱敏样本）
python tests/test_crypto.py       # 加解密与示例数据
node tests/node_roundtrip.mjs     # 浏览器解密链路（WebCrypto）
node --test tests/test_study_plan.mjs # 时间安排验证、汇总与本地存储（Node.js 22.7+）
python tests/make_sample.py       # 重新生成演示数据（口令 demo-pass）

# 本地预览网页
copy tests/fixtures/sample.enc.json web/data/schedule.enc.json
python -m http.server 8000 --directory web
# 浏览器打开 http://localhost:8000，口令 demo-pass
```

## 项目结构

```text
.github/workflows/deploy.yml   收到推送后部署到 GitHub Pages
.github/workflows/android.yml  自动构建 APK 并发布到 Releases
android/                       Android 壳工程（WebView 加载 web/ 里的页面）
scripts/local_update.py        本机同步：抓取 → 加密 → 提交 → 推送
scripts/local_update.bat       双击运行上面这个脚本
scripts/api_push.py            git 端口被墙时改走 GitHub API 推送
scripts/install_task.bat       注册每日计划任务
scripts/fetch_schedule.py      命令行抓取入口（可单独使用）
scripts/hhu/auth.py            统一身份认证登录（curl_cffi + AES 密码加密）
scripts/hhu/parse.py           课表页与教学周历页解析
scripts/hhu/crypto.py          PBKDF2 + AES-256-GCM 口令加密
web/index.html                 页面骨架
web/app.js                     前端逻辑（解密、周次计算、渲染）
web/style.css                  样式（含深色模式）
web/sw.js                      Service Worker（离线缓存）
web/manifest.webmanifest       PWA 清单
web/data/schedule.enc.json     加密后的课表（由本机同步生成）
tests/                         解析、加密与浏览器解密链路测试
```

## 技术细节

- **WAF 与 IP 拦截**：学校 WAF 会掐断 Python `requests` 的 TLS 握手，抓取必须用 `curl_cffi` 模拟 Chrome 指纹；而数据中心 IP 属于另一个维度的拦截，只能换网络位置（见上文）。
- **页面编码**：课表页没有 charset 声明，实际是 UTF-8，必须显式解码，否则中文乱码。
- **课表格子解析**：课程信息在 `div.kbcontent` 里，字段靠 `<font>` 的 `title` 属性区分；同一格内的多段安排（如第 2-11 周 + 第 12 周）会被拆成多条记录。
- **周次判断**：前端按所选周次过滤课程，支持多段周次与单双周；非本周课程以虚线灰显。
- **加密**：PBKDF2-SHA256（200000 次）派生 256 位密钥，AES-256-GCM 加密，浏览器用原生 `crypto.subtle` 解密，无第三方库。
- **推送容错**：`local_update.py` 先试 `git push`，失败后自动调用 `api_push.py`，用 Git Data API 构造同样的提交，绕开被阻断的 git 端口。

# 河海课表 PWA

打开就是一个周课表：数据自动从河海大学教务系统同步，手机上添加到主屏幕后可以像 App 一样使用，没网也能看。

## 它长什么样

- 首屏是周一~周日 × 五个大节的课表网格，顶栏显示「第 X 周」和日期区间，左右箭头切周
- 点课程格子弹出详情：教师、教室、节次时间、周次范围、课程群号
- 非本周的课程灰显（虚线框），无固定时间的课程（如实习、实践课）列在课表下方
- 「现在是第几周」由教务系统教学周历自动推算，也可以在设置里手动微调

## 工作原理

```text
GitHub Actions（每天北京时间 06:30）
   └─ 登录统一身份认证（模拟 Chrome 指纹，绕过 WAF）
      └─ 解析「学期理论课表」+「教学周历」
         └─ 用 SCHEDULE_PASSPHRASE 加密成 web/data/schedule.enc.json
            └─ 提交到仓库并部署到 GitHub Pages

手机 Chrome 打开页面
   └─ 输入一次口令 → WebCrypto 解密 → 存本机 → 离线可用
```

课表只在真的发生变化时才提交，所以仓库历史很干净；每次同步都会重新部署一次网站。

## 一次性配置（约 5 分钟）

1. 注册或登录 [GitHub](https://github.com)。
2. 新建一个仓库，可见性选 **Public**（免费账号的 GitHub Pages 只支持公开仓库；课表数据是加密的，见下文隐私说明）。
3. 把本项目推送到该仓库（或直接用网页上传文件）。
4. 打开仓库 **Settings → Secrets and variables → Actions**，依次添加三个 Secret：

   | 名称 | 值 |
   | --- | --- |
   | `HHU_USERNAME` | 你的学号 |
   | `HHU_PASSWORD` | 你的统一身份认证密码 |
   | `SCHEDULE_PASSPHRASE` | 自己定一个口令（手机解锁课表要用，请记牢） |

5. 打开 **Settings → Pages**，把 *Build and deployment* 的 Source 设为 **GitHub Actions**。
6. 打开 **Actions → 同步课表数据 → Run workflow**，等它跑完（约 1 分钟）。

完成后网站地址是：`https://<你的用户名>.github.io/<仓库名>/`

## 手机上使用（安卓 Chrome）

1. 用 Chrome 打开上面的网址。
2. 输入 `SCHEDULE_PASSPHRASE` 的口令，解锁课表。
3. 点右上角 ⋮ → 「安装应用 / 添加到主屏幕」。
4. 之后从桌面图标直接打开，离线也能看；下拉或进设置点「立即同步」可拉取最新数据。

## 日常维护

| 情况 | 做法 |
| --- | --- |
| 调课、换教室 | 等第二天自动同步，或在 Actions 里手动 Run workflow |
| 教务系统改了密码 | 更新仓库 Secret `HHU_PASSWORD` |
| 忘记口令 | 换一个新口令更新 Secret，然后在手机上重新输入 |
| 想换学期 | 无需操作，新学期教务系统会自动把新课表放上来 |

## 隐私说明

- 仓库是公开的，但 `web/data/schedule.enc.json` 用 **AES-256-GCM** 加密，口令是 PBKDF2-SHA256（20 万次迭代）派生的，没有口令无法还原内容。
- 学号和密码只存在于 GitHub Secrets（加密存储）和本机 `scripts/local_secrets.json`（已被 `.gitignore` 忽略），不会进入代码或网页。
- 网页把你的口令存在手机浏览器的 localStorage 里，只用于自动同步时解密；点设置里的「清除本机数据」可以全部删掉。
- 仓库里的测试样本是**脱敏**过的（课程名、教师、教室、学号都换成了虚构值）。

## 备用方案：本地更新

如果 GitHub Actions 的机房 IP 被学校风控拦截（表现为 workflow 报错「抓取失败」）：

1. 复制 `scripts/local_secrets.example.json` 为 `scripts/local_secrets.json`，填入真实学号、密码和同一个口令；
2. 双击 `scripts/local_update.bat`，脚本会抓取、加密、提交并推送，其余流程完全一样。

## 常见问题

- **解锁时提示「服务器上还没有课表数据」**：workflow 还没成功跑过，先去 Actions 手动运行一次。
- **提示「口令不对」**：手机输入的口令和 `SCHEDULE_PASSPHRASE` 不一致。
- **「现在是第几周」不对**：进设置用「起始前移一周 / 后移一周」校正，或核对教务系统教学周历后「恢复自动日期」。
- **同步失败但仍能看课表**：正常，用的是本机缓存；联网后重试即可。
- **教务系统改版导致抓取失败**：`tests/test_parse.py` 会先报错，按新页面结构更新 `scripts/hhu/parse.py` 即可。

## 本地开发与测试

```bash
pip install -r scripts/requirements.txt

python tests/test_parse.py        # 解析回归测试（用脱敏样本）
python tests/test_crypto.py       # 加解密与示例数据
node tests/node_roundtrip.mjs     # 浏览器解密链路（WebCrypto）
python tests/make_sample.py       # 重新生成演示数据（口令 demo-pass）

# 本地预览网页：把演示数据放到数据目录后启动静态服务
copy tests/fixtures/sample.enc.json web/data/schedule.enc.json
python -m http.server 8000 --directory web
# 浏览器打开 http://localhost:8000，口令 demo-pass
```

抓取脚本也可以单独运行（不提交任何明文）：

```bash
python scripts/fetch_schedule.py --plain build/schedule.json \
    --secrets-file scripts/local_secrets.json
```

## 项目结构

```text
.github/workflows/sync.yml     定时抓取 + 部署 Pages
scripts/fetch_schedule.py      抓取入口（登录、解析、加密输出）
scripts/hhu/auth.py            统一身份认证登录（curl_cffi + AES 密码加密）
scripts/hhu/parse.py           课表页与教学周历页解析
scripts/hhu/crypto.py          PBKDF2 + AES-256-GCM 口令加密
scripts/local_update.bat       备用：本地抓取并推送
web/index.html                 页面骨架
web/app.js                     前端逻辑（解密、周次计算、渲染）
web/style.css                  样式（含深色模式）
web/sw.js                      Service Worker（离线缓存）
web/manifest.webmanifest       PWA 清单
web/data/schedule.enc.json     加密后的课表（由 workflow 生成）
tests/                         解析、加密与浏览器解密链路测试
```

## 技术细节

- **WAF 与 TLS 指纹**：教务系统的 WAF 会直接掐断 Python `requests` 的 TLS 握手，抓取必须用 `curl_cffi` 模拟 Chrome 指纹。
- **页面编码**：课表页没有 charset 声明，实际是 UTF-8，必须显式解码，否则中文乱码。
- **课表格子解析**：课程信息在 `div.kbcontent` 里，字段靠 `<font>` 的 `title` 属性区分；同一格内的多段安排（如第 2-11 周 + 第 12 周）会被拆成多条记录。
- **周次判断**：前端按所选周次过滤课程，支持多段周次与单双周；非本周课程以虚线灰显。
- **加密**：PBKDF2-SHA256（200000 次）派生 256 位密钥，AES-256-GCM 加密，浏览器用原生 `crypto.subtle` 解密，无第三方库。

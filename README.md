# ModelScope Keep Alive

本仓库当前只保留 ModelScope 私有创空间保活相关脚本：

- `login_and_save.py`：首次手动登录并保存 Playwright 登录态
- `modelscope_keep_alive.py`：复用登录态，持续访问并保活创空间页面
- `modelscope_keep_alive.template.json`：配置模板
- `Dockerfile`、`docker-compose.yml`：用于 Synology NAS / Docker 持久运行

当前目标地址示例：

```text
https://www.modelscope.cn/studios/haso2007/openclaw_computer/summary
```

## 已验证的结论

1. 私有创空间在未登录状态下通常会显示 `404 / sorry the page you visited does not exist`，这不是脚本崩溃，而是未授权访问。
2. 最稳的流程是：先在你自己的浏览器里登录，再运行 `login_and_save.py` 保存登录态，最后运行 `modelscope_keep_alive.py`。
3. 即使复用 Edge 的 `Profile 2`，只要浏览器是被 Playwright 驱动的，网站仍可能识别为自动化环境。
4. 已实际观察到页面可显示“运行中”，但 noVNC 区域仍可能提示“无法连接到服务器”。
5. 因此当前方案更接近“页面会话保活”，还不能证明一定能维持 noVNC 远程连接层的活跃状态。
6. 是否真正能防止空间被回收，最终要看跨过平台空闲阈值后的实际结果。

## 文件说明

- `login_and_save.py`：打开浏览器，手动登录后保存 `modelscope_auth.json`；如需复用现有 Edge 的代理等配置，建议先用该 Profile 打开目标站点确认可访问，再关闭 Edge 后让脚本接管同一个 Profile
- `modelscope_keep_alive.py`：周期性访问页面并做轻量保活
- `modelscope_keep_alive.json`：本地配置文件，不提交到 Git
- `modelscope_auth.json`：本地登录态文件，不提交到 Git
- `modelscope_keep_alive.log`：运行日志，不提交到 Git
- `nas-data/`：Docker 持久化目录，给 NAS 上的容器使用

## 安装依赖

本机直接运行时需要：

```bash
pip install playwright
playwright install chromium
```

如果在 Windows 上直接使用系统 Edge，通常只需要安装 Python 包本身；脚本会在必要时尝试补装缺失依赖。

## 配置

复制模板：

```bash
cp modelscope_keep_alive.template.json modelscope_keep_alive.json
```

Windows CMD：

```bat
copy modelscope_keep_alive.template.json modelscope_keep_alive.json
```

模板内容：

```json
{
  "target_url": "https://www.modelscope.cn/studios/haso2007/openclaw_computer/summary",
  "cookies": "",
  "check_interval": 1800,
  "auth_file": "modelscope_auth.json",
  "browser_channel": "msedge",
  "last_updated": ""
}
```

字段说明：

- `target_url`：要保活的创空间地址
- `check_interval`：检查间隔，单位秒，默认 `1800`，也就是 30 分钟
- `auth_file`：登录态文件，默认 `modelscope_auth.json`
- `browser_channel`：Windows 推荐 `msedge`，Linux / Docker 推荐 `chromium`

## 推荐流程

### 1. 首次登录并保存登录态

Windows 推荐：

```powershell
python login_and_save.py --browser-channel msedge
```

Linux 或通用 Chromium：

```bash
python login_and_save.py --browser-channel chromium
```

执行后：

1. 在弹出的浏览器里手动登录 ModelScope。
2. 确认私有创空间页面已经可访问，不再是 `404`。
3. 回到终端按 Enter，保存登录态。

### 2. 尝试复用现有 Edge Profile

如果你希望尽量沿用当前 Edge Profile 里的代理、浏览器设置、扩展或已有登录环境，推荐按下面顺序操作：

1. 先用你平时在用的 Edge Profile（例如 `Default` 或 `Profile 2`）手动打开目标创空间地址，确认页面在这个 Profile 下本身就能正常访问。
2. 确认访问正常后，完全关闭所有 Edge 窗口和后台进程。
3. 再运行 `login_and_save.py`，让 Playwright 复用同一个 User Data Dir 和 Profile Directory。

如果当前使用的是默认 Profile `Default`：

```powershell
python login_and_save.py --browser-channel msedge --edge-user-data-dir "$env:LOCALAPPDATA\Microsoft\Edge\User Data" --profile-directory "Default"
```

如果你不确定自己在用哪个 Profile，可以先查出真实的 Profile 目录名，再把它原样填进 `--profile-directory`。

方法 1：直接列出本机 Edge 的 Profile 目录

```powershell
Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Edge\User Data" -Directory |
  Where-Object { $_.Name -eq "Default" -or $_.Name -like "Profile *" } |
  Select-Object -ExpandProperty Name
```

常见输出可能是：

```text
Default
Profile 1
Profile 2
Profile 3
```

这时命令里的 `--profile-directory` 就填写上面显示的目录名本身，而不是 Edge 界面上显示的昵称。例如如果目录名是 `Profile 3`，就写：

```powershell
python login_and_save.py --browser-channel msedge --edge-user-data-dir "$env:LOCALAPPDATA\Microsoft\Edge\User Data" --profile-directory "Profile 3"
```

方法 2：直接在 Edge 里确认当前窗口对应的 Profile 路径

1. 用你想复用的那个 Edge Profile 打开 `edge://version`
2. 找到 `Profile path`
3. 看路径最后一级目录名，例如：

```text
C:\Users\Dell\AppData\Local\Microsoft\Edge\User Data\Profile 2
```

上面这个例子里，应该写入命令的是：

```powershell
--profile-directory "Profile 2"
```

如果要显式复用其他 Edge Profile，例如 `Profile 2`：

```powershell
python login_and_save.py --browser-channel msedge --edge-user-data-dir "$env:LOCALAPPDATA\Microsoft\Edge\User Data" --profile-directory "Profile 2"
```

注意：

- 必须先完全关闭所有 Edge 窗口和后台进程，否则用户目录被占用时会启动失败。
- Edge 界面里显示的“个人 / 工作 / 某某账号”这类名称，不一定等于磁盘目录名；命令里要以实际目录名为准，比如 `Default`、`Profile 1`、`Profile 2`。
- 这里是“复用同一个 Profile 目录”，不是新建一个干净浏览器；这样更容易沿用该 Profile 已有的代理和浏览器侧配置。
- 即便成功打开，也仍可能被站点识别为自动化浏览器。
- 已观察到页面可打开，但 noVNC 仍可能显示“无法连接到服务器”。

## 运行保活

默认无头模式：

```bash
python modelscope_keep_alive.py
```

指定检查间隔，例如 10 分钟或 1 小时：

```bash
python modelscope_keep_alive.py --check-interval 600
python modelscope_keep_alive.py --check-interval 3600
```

有头模式：

```bash
python modelscope_keep_alive.py --headed
```

指定浏览器通道：

```bash
python modelscope_keep_alive.py --browser-channel msedge
python modelscope_keep_alive.py --browser-channel chromium
```

当前脚本行为：

- 默认每 30 分钟检查一次。
- 巡检阶段不会每轮都重复点击 `运行` / `Open`。
- 如果检测到“长时间未激活 / 正在重新部署 / 休眠 / 待运行”等提示，会尝试重新激活。
- 首次打开页面时，如果页面上已经出现明显入口按钮，当前版本仍可能做一次激活尝试。

## 后台运行

### Windows 控制台方式

```powershell
python modelscope_keep_alive.py
```

如果你是从可见的控制台窗口启动，手动关闭那个窗口会直接结束脚本进程。

### Windows 真后台方式

```powershell
Start-Process -FilePath pythonw -ArgumentList "modelscope_keep_alive.py","--check-interval","1800" -WorkingDirectory "$PWD"
```

### Linux / WSL / Git Bash

```bash
nohup python modelscope_keep_alive.py > /dev/null 2>&1 &
echo $!
```

## Synology NAS / Docker

推荐做法是：

1. 先在本机完成一次登录，拿到 `modelscope_auth.json`。
2. 再把登录态和配置文件复制到 NAS 上的 `nas-data/` 目录。
3. 最后由 Synology Container Manager 或 `docker compose` 长期运行。

仓库里已经提供这些 Docker 文件：

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

容器运行时约定：

- 容器内代码目录是 `/app`
- 持久化状态目录是 `/data`
- `MODELSCOPE_STATE_DIR=/data` 用来保存配置、登录态和日志
- 容器启动时会强制使用 `chromium`，不会沿用 Windows 配置里的 `msedge`

首次迁移到 NAS 时，把这两个文件复制到 `nas-data/`：

- `nas-data/modelscope_keep_alive.json`
- `nas-data/modelscope_auth.json`

然后在 NAS 项目目录执行：

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

停止：

```bash
docker compose down
```

说明：

- `nas-data/modelscope_keep_alive.log` 会保留脚本运行日志。
- 如果容器重建，只要 `nas-data/` 还在，登录态和配置就会继续复用。
- 对于私有空间，通常不建议在 NAS 容器里跑 `login_and_save.py` 做首次登录，还是先在本机完成登录再迁移更稳。

## 如何确认是否仍在运行

查看日志文件：

```text
modelscope_keep_alive.log
```

典型启动日志应包含：

```text
ModelScope Studio Keep-Alive Started (Playwright)
Loaded saved login state from ...\modelscope_auth.json
Opening target page: https://www.modelscope.cn/studios/...
[OK] Page loaded - Title: openclaw_computer · 创空间
```

之后应按 `check_interval` 周期看到类似日志：

```text
[OK] Check #1 - alive - Title: openclaw_computer · 创空间 - State: complete
```

## 迁移到其它服务器

如果先在本机完成一次登录，再迁移到其它服务器运行，至少需要带上：

- `modelscope_keep_alive.py`
- `modelscope_keep_alive.json`
- `modelscope_auth.json`

额外要求：

- 目标服务器能访问 `modelscope.cn`
- 目标服务器能安装并运行 Playwright

如果迁移后仍出现登录失效、`404` 或行为异常，建议直接在目标服务器重新执行一次 `login_and_save.py`。

## 当前限制

- 这个仓库当前解决的是“私有创空间页面层保活”。
- 还没有证明它能稳定维持 noVNC 远程连接层活跃。
- 如果后续实测仍然出现“长时间未激活，正在重新部署”，说明平台判定不只看页面访问，可能还依赖远程连接层。

## 本地文件

这些文件不会提交到 Git：

- `modelscope_keep_alive.json`
- `modelscope_auth.json`
- `modelscope_keep_alive.log`
- `nas-data/` 里的实际运行文件

不要公开分享登录态文件或 Cookie。

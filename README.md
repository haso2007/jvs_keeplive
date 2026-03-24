# ModelScope Keep Alive

本仓库当前只保留 ModelScope 私有创空间保活相关脚本：

- `login_and_save.py`：首次手动登录并保存 Playwright 登录态
- `modelscope_keep_alive.py`：复用登录态，持续访问并保活创空间页面
- `modelscope_keep_alive.template.json`：配置模板

当前目标地址示例：

```text
https://www.modelscope.cn/studios/haso2007/openclaw_computer/summary
```

## 已验证的结论

1. 私有创空间在未登录状态下通常会显示 `404 / sorry the page you visited does not exist`，这不是脚本崩溃，而是未授权访问。
2. 最稳的流程是：先在自己的浏览器里登录，再运行 `login_and_save.py` 保存登录态，最后运行 `modelscope_keep_alive.py`。
3. 即使复用 Edge 的 `Profile 2`，只要浏览器是被 Playwright 驱动的，网站仍可能识别为自动化环境。
4. 已实际观察到：页面可以正常显示“运行中”，但 noVNC 区域仍可能提示“无法连接到服务器”。
5. 因此当前方案更接近“页面会话保活”，还不能证明一定能维持 noVNC 远程连接层的活跃状态。
6. 是否真正能防止空间被回收，最终要以跨过平台空闲阈值后的实际结果为准。

## 文件说明

- `login_and_save.py`：打开浏览器，手动登录后保存 `modelscope_auth.json`
- `modelscope_keep_alive.py`：周期性访问页面并做轻量保活
- `modelscope_keep_alive.json`：本地配置文件，不提交到 Git
- `modelscope_auth.json`：本地登录态文件，不提交到 Git
- `modelscope_keep_alive.log`：运行日志，不提交到 Git

## 安装依赖

Python 3.9+：

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
- `browser_channel`：Windows 推荐 `msedge`，其他环境可用 `chromium`

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

1. 在弹出的浏览器里手动登录 ModelScope
2. 确认私有创空间页面已经可访问，不再是 `404`
3. 回到终端按 Enter，保存登录态

### 2. 尝试复用现有 Edge Profile

如果要显式复用现有 Edge Profile，例如 `Profile 2`：

```powershell
python login_and_save.py --browser-channel msedge --edge-user-data-dir "$env:LOCALAPPDATA\Microsoft\Edge\User Data" --profile-directory "Profile 2"
```

注意：

- 必须先完全关闭所有 Edge 窗口和后台进程，否则用户目录被占用时会启动失败
- 即便成功打开，也仍可能被站点识别为自动化浏览器
- 已观察到页面可打开，但 noVNC 仍可能显示“无法连接到服务器”

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

- 默认每 30 分钟检查一次
- 巡检阶段不会每轮都重复点击 `运行` / `Open`
- 如果检测到“长时间未激活 / 正在重新部署 / 休眠 / 待运行”等提示，会尝试重新激活
- 首次打开页面时，如果页面上已经出现明显入口按钮，当前版本仍可能做一次激活尝试

## 后台运行

### Windows 控制台方式

```powershell
python modelscope_keep_alive.py
```

如果你是从可见的控制台窗口启动，手动关闭那个窗口会直接结束脚本进程。

### Windows 真后台方式

使用 `pythonw.exe` 启动时不会弹控制台窗口：

```powershell
Start-Process -FilePath pythonw -ArgumentList "modelscope_keep_alive.py","--check-interval","1800" -WorkingDirectory "$PWD"
```

### Linux / WSL / Git Bash

```bash
nohup python modelscope_keep_alive.py > /dev/null 2>&1 &
echo $!
```

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

- 这个仓库现在解决的是“私有创空间页面层保活”
- 还没有证明它能稳定维持 noVNC 远程连接层活跃
- 如果后续实测仍然出现“长时间未激活，正在重新部署”，说明平台判定不只看页面访问，可能还依赖远程连接层

## 本地文件

这些文件不会提交到 Git：

- `modelscope_keep_alive.json`
- `modelscope_auth.json`
- `modelscope_keep_alive.log`

不要公开分享登录态文件或 Cookie。

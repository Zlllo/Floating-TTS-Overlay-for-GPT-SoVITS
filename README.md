# Floating TTS Overlay for GPT-SoVITS
**一个专为 Windows 无边框游戏设计的极简、轻量、无延迟 GPT-SoVITS 前端悬浮窗。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🌟 简介 (Introduction)

本扩展工具允许你在进行全屏无边框（Borderless Windowed）游戏或观看全屏直播时，**直接呼出并置顶一个透明的输入框**。
只需输入想说的话，它会自动调用后端的 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) API 接口生成语音，并**在内存中毫秒级直接播放**（不生成中间缓存文件）。

### ✨ 特色功能
- 🪟 **无边框吸附置顶**：原生 Windows 样式消除边框，不挡游戏画面，可随意拖拽挪动位置。
- ⚙️ **图形化配置 UI（支持动态换模）**：告别黑框和修改配置文件！自带精美设置面板（小齿轮图标），自动扫描你 `GPT-SoVITS` 和 `SoVITS` 路径下的权重，**一键即可切换音色模型**，填入参考音频的提示词和语种即可极速合成。
- ⚡ **零存取无延迟**：直接利用 Windows `winsound.SND_MEMORY` 在底层内存中解码和播放音频流。这使得生成的语音能在毫无磁盘 I/O 延迟的情况下迅速传达到你的耳机里。
- 📦 **免环境安装**：利用 Python 纯自带的系统库 `tkinter`, `urllib`, `winsound` 等。只要你能跑得起 GPT-SoVITS 默认的整合包（自带的 `runtime/python` 环境），这套工具双击就能跑，**完全 0 依赖**。

## 📸 界面预览 (Screenshots)
![游戏内悬浮窗实机演示](assets/preview.png)

## 🚀 安装与启动 (Installation & Usage)

因为本作依赖原生 GPT-SoVITS 的环境提供推理服务，所以请直接将 `floating_tts.py` 和 `go-floating-tts.bat` 放在你的 `GPT-SoVITS` 根目录（包含 `api_v2.py` 的那个文件夹内）。

### 快捷启动 (推荐)
直接双击运行主目录下的：
**`go-floating-tts.bat`**
它会自动在后台打开 API 服务，并随后呼出悬浮窗。

---

### 手动分步启动 (进阶)
如果你想分别调试：
1. **启动核心 API**：
   ```bat
   runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880
   ```
2. **启动悬浮窗**：
   ```bat
   runtime\python.exe floating_tts.py
   ```

### 第三步：配置与使用
首次打开后，请：
1. 点击悬浮窗上的 **⚙ 齿轮图标** 打开 Settings 并置顶。
2. 在下拉框中选择你的 **GPT Model**（.ckpt 权重） 和 **SoVITS Model**（.pth 权重）。
3. 选择你想克隆的参考音频路径（`*.wav`），输入参考音频对应的短语（`Prompt Text`）以及语言。
4. 点击 **Save & Close**（这些配置将会存在根目录下的 `floating_config.json` 中，以后不用重复设置）。

现在，打开你的游戏，尽情游玩并在悬浮框中输入你想要让模型念出的文本吧！按下 `Enter` 或者点击发送即可播报。

## ☁️ 云端实例 + SSH 隧道模式

现在支持把 `GPT-SoVITS` 部署在云端实例上，同时保留本地悬浮窗输入体验。
推荐链路如下：

`本地浮窗输入 -> 本地 127.0.0.1:转发端口 -> SSH -L 隧道 -> 云端 127.0.0.1:API端口 -> GPT-SoVITS`

### 1. 在云端启动 GPT-SoVITS API
在你的云主机上运行：

```bash
python api_v2.py -a 127.0.0.1 -p 9880
```

这里建议继续绑定 `127.0.0.1`，让 API 只暴露给 SSH 隧道，而不是直接暴露到公网。

### 2. 本地悬浮窗如何填写
在 `Settings` 中：

1. `Run Mode` 选择 **Cloud**
2. 勾选 **Use SSH Tunnel**
3. 填写：
   - `SSH Host`：云服务器 IP 或域名
   - `SSH Port`：SSH 端口，默认 `22`
   - `SSH User`：登录用户名
   - `SSH Key`：本地私钥路径（如果你用密钥登录）
   - `Local Port`：本地转发端口，例如 `9880`
   - `Remote Host`：通常填 `127.0.0.1`
   - `Remote Port`：云端 GPT-SoVITS API 端口，例如 `9880`
   - `SSH Extra Args`：额外 SSH 参数，可选，例如 `-o StrictHostKeyChecking=no`

保存后，悬浮窗在第一次发送文本时会自动拉起 SSH 隧道。

### 3. 云端模式下几个容易填错的项

- `GPT Model`、`SoVITS Model`、`Ref Audio Path` 在 **Cloud** 模式下都应该填写云端机器上的路径。
- 你的参考音频如果只在本地存在，云端是读不到的，需要先上传到云端。
- 如果你不想走 SSH，也可以在 `Cloud` 模式里取消 `Use SSH Tunnel`，然后直接填公网可访问的 `API URL`。

### 4. 本地环境要求

- Windows 需要可用的 `ssh` 命令。一般安装系统自带的 OpenSSH Client 即可。
- 如果你使用密钥登录，确保私钥权限和路径正确。
- 若 SSH 连接失败，悬浮窗会在控制台打印错误信息，方便排查端口、密钥或用户名问题。

## 🛠️ 参数说明与进阶
- **Speed (语速)**：默认 1.0，想让角色说话快一点请设置为 1.2 等。
- **Window Opacity (透明度)**：默认 0.85，调整数值 0-1 以适应不同暗色调的游戏界面（越接近 0 越透明）。
- **Target Lang (目标合成语言)**：支持 `zh`, `en`, `ja`, `auto` (多语种)。

## 🤝 参与贡献 (Contributing)
这是一个非常简单的单文件 Python 小工具！由于是用原生 `tkinter` 写的，它还可以变得更加花哨！欢迎各位提交 PR 改进它的能力（如支持翻译组件、直播弹幕播报联动扩展等）。

## 📄 协议 (License)
使用 [MIT](LICENSE) 协议开源。
你可以自由地在你的项目中修改、分发这个扩展包，仅需保留源声明即可。

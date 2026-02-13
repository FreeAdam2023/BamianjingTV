# 局域网虚拟演播室系统 — 完整实施指南

> **目标**：macOS 运行 OBS + Web 控制台，Ubuntu GPU 服务器（RTX 5080）运行 Unreal Engine 渲染 MetaHuman 虚拟人物，实现"桌面采集 → 虚拟演播室渲染 → OBS 合成"完整闭环。

---

## 目录

1. [环境准备](#一环境准备)
2. [MetaHuman 创建与导入](#二metahuman-创建与导入)
3. [Unreal 项目搭建](#三unreal-项目搭建)
4. [SRT 流媒体配置](#四srt-流媒体配置)
5. [Web 控制台设计](#五web-控制台设计)
6. [Ubuntu 部署](#六ubuntu-部署)
7. [OBS 最终合成](#七obs-最终合成)
8. [MVP 检查清单](#八mvp-检查清单)

---

## 一、环境准备

### 1.1 网络拓扑

```
┌──────────────────┐          LAN (1Gbps+)          ┌──────────────────────┐
│    macOS (控制端)   │ ◄────── 192.168.x.0/24 ──────► │ Ubuntu GPU 服务器       │
│                    │                                 │ (RTX 5080, 16GB VRAM) │
│  - OBS Studio      │   SRT :9000 (桌面 → UE)         │  - UE5 渲染引擎         │
│  - Web 控制台       │   SRT :9001 (UE → OBS)          │  - MetaHuman 角色       │
│  - Chrome 浏览器    │   HTTP :8080 (UE 控制)          │  - Pixel Streaming     │
│  - SceneMind API   │   HTTP :8001 (SceneMind API)   │                        │
└──────────────────┘                                 └──────────────────────┘
```

**IP 规划建议**：
| 设备 | 建议 IP | 用途 |
|------|---------|------|
| macOS | 192.168.1.100 | OBS + 控制台 |
| Ubuntu | 192.168.1.200 | UE5 渲染 |

> 确保两台机器在同一子网，ping 延迟 < 1ms。

### 1.2 macOS 安装 Unreal Engine 5

1. **下载 Epic Games Launcher**
   - 访问 https://www.unrealengine.com/download
   - 下载 macOS 版 Epic Games Launcher，安装并登录 Epic 账号

2. **安装 UE 5.4+**（推荐 5.4 或 5.5）
   - 打开 Epic Games Launcher → Unreal Engine → Library
   - 点击 "+" 安装引擎版本，选择 **5.4.x**
   - 安装选项：勾选 "Starter Content"，可跳过 "Templates"
   - 安装大小约 25-40 GB，预留足够磁盘空间

3. **确认内置插件可用**
   - UE5 已内置以下所需插件，无需额外安装：
     - **Fab (原 Quixel Bridge)** — MetaHuman 导入（UE5.4+ 内置）
     - **Remote Control API** — HTTP 控制端点（内置，需在 Plugins 中启用）
     - **Pixel Streaming** — WebRTC 视频输出（内置）
   - 这些插件也需要在 Ubuntu 打包时启用

> **注意**：macOS 上的 UE5 仅用于开发和编辑场景。最终渲染在 Ubuntu GPU 服务器上运行。

### 1.3 macOS 安装 OBS Studio

```bash
# Homebrew 安装
brew install --cask obs

# 或从官网下载
# https://obsproject.com/download
```

安装后启动 OBS，确认：
- 可以采集桌面（Screen Capture）
- 可以添加 Media Source（后续用于接收 SRT 流）

### 1.4 Ubuntu GPU 服务器准备

#### 1.4.1 NVIDIA 驱动

```bash
# 查看 GPU
lspci | grep -i nvidia

# 安装推荐驱动（RTX 5080 Blackwell 架构需要 570+ 驱动）
sudo apt update
sudo ubuntu-drivers install

# 验证
nvidia-smi
# 应显示 RTX 5080, 驱动版本 570+, CUDA 12.x
```

#### 1.4.2 Vulkan 支持

```bash
# 安装 Vulkan SDK
sudo apt install -y vulkan-tools libvulkan-dev mesa-vulkan-drivers

# 验证
vulkaninfo | head -20
# 应显示 RTX 5080 设备
```

#### 1.4.3 X11 桌面环境（用于 UE5 渲染窗口）

```bash
# 安装轻量级桌面环境
sudo apt install -y xorg xserver-xorg-video-nvidia openbox

# 或安装完整桌面（如需远程操作）
sudo apt install -y ubuntu-desktop-minimal

# 配置自动登录（systemd）
sudo systemctl set-default graphical.target
```

**无头渲染方案**（无显示器时）：

```bash
# 使用虚拟显示
sudo apt install -y xvfb
Xvfb :1 -screen 0 1920x1080x24 &
export DISPLAY=:1

# 或使用 NVIDIA 虚拟 GPU（推荐）
# 创建 /etc/X11/xorg.conf 指定 GPU 渲染
sudo nvidia-xconfig --allow-empty-initial-configuration
```

#### 1.4.4 安装 UE5 (Linux)

```bash
# 方法 1: 使用 Epic Games Launcher（推荐）
# 在 Ubuntu 桌面环境下下载 https://www.unrealengine.com/download → Linux
# 通过 Launcher 安装 UE5 编辑器，在 Ubuntu 上直接打包 Linux 目标

# 方法 2: 从源码编译（高级用户）
git clone https://github.com/EpicGames/UnrealEngine.git
cd UnrealEngine
./Setup.sh && ./GenerateProjectFiles.sh && make
```

> **重要**：macOS 版 UE5 Editor **不支持**交叉编译到 Linux（缺少 Linux toolchain）。正确的工作流是：
> 1. 在 macOS 上开发和编辑场景
> 2. 将项目通过 Git/Perforce 同步到 Ubuntu
> 3. 在 Ubuntu 上用 UE5 Editor 执行 `File → Package Project → Linux`
>
> 或者使用 Unreal Automation Tool (UAT) 在 Ubuntu 上命令行打包：
> ```bash
> /path/to/UE5/Engine/Build/BatchFiles/RunUAT.sh BuildCookRun \
>   -project=/path/to/VirtualStudio.uproject \
>   -platform=Linux -configuration=Shipping -cook -stage -pak -archive
> ```

---

## 二、MetaHuman 创建与导入

### 2.1 在 MetaHuman Creator 创建角色

1. **访问 MetaHuman Creator**
   - 打开浏览器，访问 https://metahuman.unrealengine.com
   - 使用 Epic Games 账号登录

2. **创建角色**
   - 点击 "Create MetaHuman"
   - 选择一个基础模板，或从头开始
   - 调整面部特征：脸型、眼睛、鼻子、嘴巴、肤色
   - 调整发型和服装
   - 点击右上角 "Download" → 会提示通过 Quixel Bridge 下载

3. **设计建议**
   - 选择亚洲面孔模板作为基础（更符合中文教学场景）
   - 服装选择商务休闲风（适合演播室场景）
   - 导出时选择最高质量（Epic Quality）

### 2.2 通过 Fab 导入到 UE5

> **注意**：UE5.4+ 已将 Quixel Bridge 替换为 **Fab**（Epic 的统一资产市场）。

1. **在 UE5 中打开 Fab**
   - 菜单：Window → Fab
   - 登录同一 Epic 账号

2. **下载 MetaHuman**
   - 在 Fab 中找到 "My MetaHumans"（或搜索你创建的角色名）
   - 选择角色，点击 "Add to Project"
   - 等待下载和导入完成

3. **导入完成后**
   - 角色资产位于 `Content/MetaHumans/{YourCharacterName}/`
   - 包含 Skeletal Mesh、Animation Blueprint、Material 等

### 2.3 放置到场景 + 设置坐姿动画

1. **放置角色**
   - 将 `BP_{YourCharacterName}` 从 Content Browser 拖入场景
   - 调整 Transform：位于桌子后方，面朝摄像机

2. **创建坐姿动画 Blueprint**

   ```
   // 在 Animation Blueprint 中
   步骤：
   a. 打开 Content/MetaHumans/{Name}/BP_{Name}_AnimBP
   b. 在 AnimGraph 中添加 "Blend Space" 节点
   c. 导入坐姿 Idle 动画（Marketplace 免费资源：
      - "Sitting Idle Pack" 或 "Office Animations")
   d. 设置循环播放：Sequence → Loop
   ```

3. **推荐动画资源**（Marketplace 免费/低价）
   - **Sitting Idle Animation Pack** — 坐姿静态循环
   - **Business Casual Animations** — 商务场景动画
   - **Talking Gestures Pack** — 说话手势动画

4. **Blueprint 设置**

   在角色 Blueprint 中添加变量：
   | 变量名 | 类型 | 用途 |
   |--------|------|------|
   | `CurrentAnimation` | FName | 当前播放的动画 |
   | `BlendWeight` | Float | 动画混合权重 |
   | `IsIdle` | Bool | 是否处于空闲状态 |

---

## 三、Unreal 项目搭建

### 3.1 创建项目

1. 打开 UE5 → New Project → **Blank**
2. 设置：
   - Target: **Desktop / Console**
   - Quality: **Maximum**
   - Starter Content: **勾选**
3. 项目命名：`VirtualStudio`
4. 启用插件（Edit → Plugins）：
   - **Media Framework** ✓（内置）
   - **Remote Control API** ✓（内置，提供 HTTP 控制端点）
   - **Remote Control Web Interface** ✓（内置，可选 Web UI）
   - **Pixel Streaming** ✓（内置）
   - **MetaHuman** ✓（内置）
   - **NDI IO Plugin** ✓（需从 Marketplace/Fab 安装，用于视频输入）
   - **LiveLink** ✓（可选，用于面部捕捉）

### 3.2 场景结构

```
World Outliner 层级：
├── VirtualStudioLevel
│   ├── Lighting
│   │   ├── DirectionalLight (太阳光/主光源)
│   │   ├── SkyLight (环境光)
│   │   ├── RectLight_Key (主光)
│   │   ├── RectLight_Fill (补光)
│   │   └── RectLight_Back (轮廓光)
│   ├── Environment
│   │   ├── SkyAtmosphere
│   │   ├── VolumetricCloud
│   │   ├── ExponentialHeightFog
│   │   └── FloorWindow (落地窗 + 外景)
│   ├── Furniture
│   │   ├── SM_Desk (桌子)
│   │   ├── SM_Chair (椅子)
│   │   └── SM_Monitor (显示器模型)
│   ├── Screens
│   │   ├── SM_MainScreen (主屏幕 — 接收 SRT 桌面视频)
│   │   └── SM_SideScreen (侧屏 — 可选)
│   ├── Characters
│   │   └── BP_MetaHumanHost (MetaHuman 主持人)
│   └── Cameras
│       ├── CineCamera_Main (主机位)
│       ├── CineCamera_Close (特写)
│       └── CineCamera_Wide (全景)
```

### 3.3 模块化 Blueprint 结构

创建以下 Blueprint Actor 用于控制各模块：

#### BP_SceneManager（场景管理器）
```
变量：
  - CurrentPreset: FName (当前场景预设名)
  - Presets: Map<FName, ScenePresetData> (预设配置)

函数：
  - SetPreset(PresetName) → 切换场景预设
  - GetCurrentPreset() → 返回当前预设
  - GetAvailablePresets() → 返回可用预设列表

场景预设示例：
  - "modern_office" — 现代办公室
  - "news_desk" — 新闻演播台
  - "podcast_studio" — 播客录音室
  - "classroom" — 教室
```

#### BP_ScreenManager（显示器管理器）
```
变量：
  - MediaPlayer: MediaPlayer (SRT 流播放器)
  - MediaTexture: MediaTexture
  - ScreenMaterial: MaterialInstanceDynamic
  - PrivacyLevel: Float (0.0 = 清晰, 1.0 = 完全模糊)

函数：
  - SetSRTSource(URL) → 设置 SRT 流地址
  - SetPrivacyLevel(Level: 0.0-1.0) → 设置雾化级别
  - ToggleScreen(bOn) → 开关屏幕
```

#### BP_CharacterManager（角色管理器）
```
变量：
  - MetaHumanActor: Reference
  - CurrentAction: FName
  - AvailableActions: Array<FName>

函数：
  - SetAction(ActionName) → 播放动作动画
  - SetExpression(ExpressionName) → 切换面部表情
  - SetLookAt(Target) → 设置注视目标
```

#### BP_WeatherManager（天气管理器）
```
变量：
  - TimeOfDay: Float (0-24, 小时)
  - WeatherType: Enum (Clear, Cloudy, Rain, Snow, Night)
  - SunIntensity: Float
  - CloudCoverage: Float

函数：
  - SetTimeOfDay(Hour) → 设置时间
  - SetWeather(Type) → 设置天气
  - SetSeason(Season) → 设置季节氛围
```

#### BP_LightingManager（灯光管理器）
```
变量：
  - KeyLightIntensity: Float
  - FillLightIntensity: Float
  - BackLightIntensity: Float
  - ColorTemperature: Float (2000-10000K)

函数：
  - SetThreePointLighting(Key, Fill, Back) → 三点布光
  - SetColorTemperature(Kelvin) → 色温
  - SetPreset(Name) → 灯光预设 (interview, dramatic, soft)
```

### 3.4 Media Framework — 接收视频流

> **重要**：UE5 的 Media Framework (ElectraPlayer) **不原生支持 SRT 协议**。支持的协议有 HLS、DASH、RTSP 和本地文件。要将 OBS 桌面画面送入 UE5，有以下方案：

#### 方案 A：NDI 桥接（推荐，延迟最低）

1. **OBS 端**：安装 [obs-ndi](https://github.com/obs-ndi/obs-ndi) 插件，启用 NDI Output
2. **Ubuntu 端**：在 UE5 安装 **NDI IO Plugin**（Fab 免费）
3. **UE5 中创建 NDI Media Source**：
   - Content Browser → 右键 → Media → NDI Media Source
   - 选择 OBS 发出的 NDI Source（自动发现）
4. NDI 在局域网走 TCP，延迟约 1-3 帧（16-50ms）

#### 方案 B：ffmpeg SRT→RTSP 转码桥接

```bash
# 在 Ubuntu 上运行 ffmpeg 将 SRT 转为 RTSP（UE5 支持 RTSP）
ffmpeg \
  -i "srt://0.0.0.0:9000?mode=listener&latency=200000" \
  -c copy -f rtsp \
  rtsp://127.0.0.1:8554/desktop
```
UE5 用 RTSP URL `rtsp://127.0.0.1:8554/desktop` 接收。

#### 方案 C：Spout/共享纹理（仅限同一台 Windows 机器，此场景不适用）

不论哪种方案，后续步骤相同：

1. **创建 Media Player**
   - Content Browser → 右键 → Media → Media Player
   - 命名 `MP_DesktopCapture`
   - 勾选 "Create Media Texture"（自动创建 `MT_DesktopCapture`）

2. **创建屏幕材质**

   ```
   Material: M_ScreenDisplay
   ├── TextureSample (MT_DesktopCapture)
   │   └── → Emissive Color
   └── ScalarParameter: "Brightness" (Default: 1.0)
       └── → Multiply → Emissive Color
   ```

3. **应用到显示器模型**
   - 选中 SM_Monitor → Material Slot → 设置为 M_ScreenDisplay
   - 在 BP_ScreenManager 的 BeginPlay 中：
     ```
     MediaPlayer.OpenSource(NDI_Source 或 RTSP_Source)
     MediaPlayer.Play()
     ```

### 3.5 隐私雾化材质

创建自定义材质实现高斯模糊效果：

```
Material: M_PrivacyScreen (基于 M_ScreenDisplay)
├── TextureSample (MT_DesktopCapture)
├── ScalarParameter: "PrivacyLevel" (0.0 - 1.0)
│   └── Controls blur amount
├── CustomExpression: GaussianBlur
│   ├── 采样 UV 偏移 (3x3 或 5x5 kernel)
│   ├── Kernel 大小 = PrivacyLevel * MaxBlurRadius
│   └── 输出加权平均颜色
├── Lerp (A=原始, B=模糊结果, Alpha=PrivacyLevel)
│   └── → Emissive Color
└── 可选：像素化效果
    ├── Floor(UV * PixelCount) / PixelCount
    └── PixelCount = Lerp(1920, 32, PrivacyLevel)
```

**Blueprint 调用**：
```
// 在 BP_ScreenManager 中
SetPrivacyLevel(Level):
  ScreenMaterialInstance.SetScalarParameterValue("PrivacyLevel", Level)
```

### 3.6 HTTP 控制端点

> **注意**：VaRest 是 HTTP **客户端**插件（从 UE5 向外发请求），不是 HTTP 服务器。要在 UE5 中创建 HTTP 监听端点，使用以下方案：

#### 方案 A：Remote Control API 插件（推荐，零代码）

UE5 内置的 **Remote Control API** 插件提供开箱即用的 HTTP + WebSocket 控制。

1. 启用插件：Edit → Plugins → 搜索 "Remote Control API" → Enable
2. 同时启用 "Remote Control Web Interface"（可选，提供调试 Web UI）
3. 默认监听端口 **30010**（HTTP）

使用方法：
- 在 Blueprint 中将变量/函数暴露给 Remote Control（右键属性 → Expose to Remote Control）
- 或在 Details 面板将 Actor 的属性标记为 Remote Control Exposed

```
// Remote Control API 端点格式（内置，无需手写）

// 获取暴露的属性列表
GET  http://192.168.1.200:30010/api/v1/preset

// 设置属性值（通过 preset 或直接调用）
PUT  http://192.168.1.200:30010/api/v1/preset/{preset_name}/property/{property_name}
Body: {"PropertyValue": 0.5}

// 调用暴露的 Blueprint 函数
PUT  http://192.168.1.200:30010/api/v1/preset/{preset_name}/function/{function_name}
Body: {"Parameters": {"Level": 0.5}}

// 自定义封装（在 BP_SceneManager 中暴露以下函数给 Remote Control）：
- SetScenePreset(PresetName: FName)
- SetWeatherType(Type: EWeatherType, TimeOfDay: Float)
- SetPrivacyLevel(Level: Float)
- SetLighting(Key: Float, Fill: Float, Back: Float, Temperature: Float)
- SetCharacterAction(Action: FName, Expression: FName)
- GetCurrentStatus() → 返回 JSON 状态
```

#### 方案 B：自定义 C++ HTTP Server（全自定义端点）

```cpp
// Source/VirtualStudio/Private/StudioHTTPServer.cpp
// 使用 FHttpServerModule 创建内嵌 HTTP 服务器
// 可自定义端点路径和 JSON 格式

#include "HttpServerModule.h"
#include "IHttpRouter.h"

void UStudioHTTPServer::StartServer()
{
    auto Router = FHttpServerModule::Get().GetHttpRouter(8080);

    // 自定义端点：/set_privacy
    Router->BindRoute(
        FHttpPath("/set_privacy"),
        EHttpServerRequestVerbs::VERB_POST,
        [this](const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete)
        {
            // Parse JSON body
            FString Body = Request.Body;
            TSharedPtr<FJsonObject> JsonObject;
            TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Body);
            FJsonSerializer::Deserialize(Reader, JsonObject);

            float Level = JsonObject->GetNumberField("level");
            // Update PrivacyLevel on ScreenManager...

            OnComplete(FHttpServerResponse::Ok());
        }
    );

    // 端点列表：
    // POST /set_scene     Body: {"preset": "modern_office"}
    // POST /set_weather   Body: {"type": "clear", "time_of_day": 14.5}
    // POST /set_privacy   Body: {"level": 0.5}
    // POST /set_lighting  Body: {"key": 0.8, "fill": 0.4, "back": 0.6, "temperature": 5500}
    // POST /set_character  Body: {"action": "talking", "expression": "smile"}
    // GET  /status        → 返回当前所有状态
}
```

> **建议**：MVP 阶段用方案 A（Remote Control API），零代码即可跑通。后续如需自定义端点路径再迁移到方案 B。

### 3.7 SRT 输出回 macOS

#### 方案 A：Pixel Streaming（推荐）

1. **启用插件**：Edit → Plugins → Pixel Streaming → Enable
2. **启动参数**：
   ```bash
   ./VirtualStudio \
     -PixelStreamingIP=0.0.0.0 \
     -PixelStreamingPort=8888 \
     -RenderOffscreen \
     -Res=1920x1080 \
     -FPS=60
   ```
3. **OBS 接收**：添加 Browser Source → `http://192.168.1.200:80`（Signalling Server 地址）

#### 方案 B：SRT 推流

使用 UE5 + ffmpeg 管道：
```bash
# 在 Ubuntu 上，将 UE5 渲染输出捕获并推送 SRT
# 方法：使用 NDI 插件 + ffmpeg 转 SRT
ffmpeg -f x11grab -s 1920x1080 -r 60 -i :1 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f mpegts "srt://192.168.1.100:9001?mode=caller"
```

---

## 四、SRT 流媒体配置

### 4.1 完整数据流

```
macOS OBS                    Ubuntu GPU Server               macOS OBS
┌───────────┐    SRT:9000    ┌────────────────┐    SRT:9001   ┌──────────┐
│ Desktop   │ ──────────►    │  UE5 Engine    │ ──────────►   │ Final    │
│ Capture   │   (桌面视频)    │  ┌──────────┐  │  (渲染输出)    │ Compose  │
│           │                │  │MetaHuman │  │              │          │
│ Screen    │                │  │  + Desk   │  │              │ Record / │
│ Capture   │                │  │  + Screen │  │              │ Stream   │
└───────────┘                │  └──────────┘  │              └──────────┘
                             └────────────────┘
                                  ↑
                            HTTP :8080
                            (控制命令)
                                  ↑
                         ┌──────────────┐
                         │ SceneMind    │
                         │ Web Console  │
                         │ /studio      │
                         └──────────────┘
```

### 4.2 macOS OBS → Ubuntu（桌面采集推流）

1. **OBS 设置**：
   - Settings → Output → Recording/Streaming
   - 添加 Custom Output (FFmpeg)：
     - Type: Custom Output (FFmpeg)
     - FFmpeg Output Type: Output to URL
     - URL: `srt://192.168.1.200:9000?mode=caller&latency=200000`
     - Container: mpegts
     - Video Encoder: libx264
     - Video Bitrate: 6000 Kbps
     - Keyframe Interval: 1s

2. **OBS 场景配置**：
   - Source: Screen Capture (macOS)
   - 分辨率: 1920x1080
   - FPS: 30（桌面采集不需要 60fps）

3. **低延迟优化**：
   ```
   SRT URL 参数说明：
   - mode=caller    → OBS 主动连接 Ubuntu
   - latency=200000 → 200ms 延迟缓冲（微秒单位）
   - pbkeylen=0     → 不加密（局域网）
   ```

### 4.3 Ubuntu UE5 接收视频流

> UE5 不原生支持 SRT，需要桥接方案（见 3.4 节）。

#### 方案 A：NDI 接收（推荐）
- 安装 NDI IO Plugin → 创建 NDI Media Source → 自动发现 OBS NDI 输出
- 无需额外配置，延迟最低

#### 方案 B：ffmpeg SRT→RTSP 桥接
```bash
# 在 Ubuntu 上运行 ffmpeg 做协议转换
ffmpeg \
  -i "srt://0.0.0.0:9000?mode=listener&latency=200000" \
  -c copy -f rtsp \
  rtsp://127.0.0.1:8554/desktop

# UE5 Media Player 中使用 RTSP URL
# Blueprint: MediaPlayer.OpenUrl("rtsp://127.0.0.1:8554/desktop")
```

### 4.4 Ubuntu UE5 → macOS OBS（渲染输出）

#### 方案 A：Pixel Streaming（推荐，最低延迟）

```bash
# Ubuntu 上启动 Pixel Streaming Signalling Server
# UE5.4+ 使用独立 npm 包（旧版 cirrus.js 已弃用）
cd /path/to/VirtualStudio/Samples/PixelStreaming/WebServers/SignallingWebServer
npm install
npm start -- --HttpPort 80 --StreamerPort 8888

# UE5 启动参数
./VirtualStudio.sh \
  -AudioMixer \
  -PixelStreamingIP=0.0.0.0 \
  -PixelStreamingPort=8888 \
  -Res=1920x1080
```

macOS OBS 接收：
- 添加 Browser Source
- URL: `http://192.168.1.200:80`
- 分辨率: 1920x1080

#### 方案 B：SRT 推流

```bash
# 使用 ffmpeg 捕获 UE5 渲染输出并推 SRT
# 在 Ubuntu 上运行：
ffmpeg \
  -video_size 1920x1080 -framerate 60 \
  -f x11grab -i :1+0,0 \
  -c:v h264_nvenc -preset p4 -tune ll \
  -b:v 10000k -maxrate 12000k -bufsize 5000k \
  -g 60 -keyint_min 60 \
  -f mpegts "srt://192.168.1.100:9001?mode=caller&latency=100000"
```

macOS OBS 接收：
- 添加 Media Source
- Input: `srt://0.0.0.0:9001?mode=listener&latency=100000`
- Input Format: mpegts

### 4.5 延迟测试

```bash
# 在 Ubuntu 上测试 SRT 连通性
srt-live-transmit \
  "srt://0.0.0.0:9000?mode=listener" \
  "srt://192.168.1.100:9001?mode=caller" \
  -v
```

预期延迟：
| 链路 | 预期延迟 |
|------|---------|
| macOS → Ubuntu SRT | 100-200ms |
| UE5 渲染 | 16ms (60fps) |
| Ubuntu → macOS SRT/Pixel Streaming | 50-150ms |
| **端到端** | **200-400ms** |

---

## 五、Web 控制台设计

Web 控制台集成到 SceneMind 项目中。

### 5.1 后端 API（FastAPI）

**路由前缀**：`/studio`

| 方法 | 路径 | 功能 | 请求体示例 |
|------|------|------|-----------|
| `POST` | `/studio/scene` | 切换场景预设 | `{"preset": "modern_office"}` |
| `POST` | `/studio/weather` | 切换天气/时间 | `{"type": "clear", "time_of_day": 14.5}` |
| `POST` | `/studio/privacy` | 设置隐私雾化 | `{"level": 0.5}` |
| `POST` | `/studio/lighting` | 调节灯光 | `{"key": 0.8, "fill": 0.4, "back": 0.6, "temperature": 5500}` |
| `POST` | `/studio/character` | 切换角色动作 | `{"action": "talking", "expression": "smile"}` |
| `GET` | `/studio/status` | 获取当前状态 | — |
| `GET` | `/studio/presets` | 获取可用预设 | — |

**通信链路**：
```
浏览器 → SceneMind API (/studio/*) → HTTP → UE5 HTTP Server (:8080)
```

SceneMind API 作为中间层，转发命令到 UE5 渲染服务器的 HTTP 端口。

### 5.2 前端页面（Next.js `/studio`）

**页面布局**：
```
┌─────────────────────────────────────────────────────────────┐
│  Header: 虚拟演播室控制台          [连接状态: ●已连接]       │
├────────────────────────┬────────────────────────────────────┤
│  场景预设               │  Pixel Streaming 预览              │
│  ┌──┐ ┌──┐ ┌──┐ ┌──┐  │  ┌──────────────────────────────┐  │
│  │办│ │新│ │播│ │教│  │  │                              │  │
│  │公│ │闻│ │客│ │室│  │  │     实时渲染预览 (iframe)      │  │
│  │室│ │台│ │室│ │  │  │  │                              │  │
│  └──┘ └──┘ └──┘ └──┘  │  │                              │  │
├────────────────────────┤  └──────────────────────────────┘  │
│  天气 / 时间            ├────────────────────────────────────┤
│  ☀️ ⛅ 🌧️ ❄️ 🌙       │  状态面板                           │
│  时间: ━━━●━━━ 14:30   │  - FPS: 60                        │
├────────────────────────┤  - GPU: 45%                        │
│  隐私雾化               │  - 分辨率: 1920x1080               │
│  ━━━━━━●━━━━ 50%       │  - SRT 输入: ✓                     │
├────────────────────────┤  - SRT 输出: ✓                     │
│  灯光                   │                                    │
│  主光: ━━━━●━━ 80%     │                                    │
│  补光: ━━●━━━━ 40%     │                                    │
│  背光: ━━━●━━━ 60%     │                                    │
│  色温: ━━━━●━━ 5500K   │                                    │
├────────────────────────┤                                    │
│  角色动作               │                                    │
│  [空闲] [说话] [点头]   │                                    │
│  [思考] [挥手] [写字]   │                                    │
└────────────────────────┴────────────────────────────────────┘
```

### 5.3 代码文件

代码实现位于：
- `backend/app/models/studio.py` — 数据模型
- `backend/app/api/studio.py` — API 端点
- `backend/app/services/studio_manager.py` — 状态管理 + UE5 通信
- `frontend/src/app/studio/page.tsx` — 控制台页面

---

## 六、Ubuntu 部署

### 6.1 UE5 项目打包

在 **Ubuntu** 上用 UE5 Editor 或 UAT 命令行打包（macOS 不支持交叉编译到 Linux）：

1. **同步项目到 Ubuntu**
   ```bash
   # 从 macOS 同步项目文件到 Ubuntu
   rsync -avz --progress /path/to/VirtualStudio/ user@192.168.1.200:/home/user/VirtualStudio/
   ```

2. **在 Ubuntu 上打包**
   ```bash
   # 方法 A：UE5 Editor GUI
   # 打开项目 → File → Package Project → Linux

   # 方法 B：UAT 命令行（推荐，可脚本化）
   /opt/UnrealEngine/Engine/Build/BatchFiles/RunUAT.sh BuildCookRun \
     -project=/home/user/VirtualStudio/VirtualStudio.uproject \
     -platform=Linux -configuration=Shipping \
     -cook -stage -pak -archive \
     -archivedirectory=/opt/virtual-studio
   ```

3. **部署到运行目录**
   ```bash
   # 打包后目录结构
   LinuxNoEditor/
   ├── VirtualStudio.sh          # 启动脚本
   ├── VirtualStudio/
   │   ├── Binaries/Linux/
   │   ├── Content/
   │   └── ...
   └── Engine/

   # 上传
   rsync -avz --progress LinuxNoEditor/ user@192.168.1.200:/opt/virtual-studio/
   ```

### 6.2 服务器运行配置

#### systemd service 文件

```ini
# /etc/systemd/system/virtual-studio.service
[Unit]
Description=Virtual Studio UE5 Renderer
After=network.target graphical.target
Requires=graphical.target

[Service]
Type=simple
User=studio
Group=studio
WorkingDirectory=/opt/virtual-studio
Environment="DISPLAY=:0"
Environment="SDL_VIDEODRIVER=x11"
ExecStart=/opt/virtual-studio/VirtualStudio.sh \
  -RenderOffscreen \
  -Res=1920x1080 \
  -FPS=60 \
  -PixelStreamingIP=0.0.0.0 \
  -PixelStreamingPort=8888 \
  -AudioMixer \
  -nosplash \
  -nosound \
  -log
Restart=on-failure
RestartSec=10
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable virtual-studio
sudo systemctl start virtual-studio
sudo systemctl status virtual-studio
```

### 6.3 性能调优

| 设置 | 推荐值 | 说明 |
|------|--------|------|
| Lumen GI | **开** | RTX 5080 足够 |
| Lumen Reflections | **开** | 反射质量好 |
| Path Tracing | **关** | 太消耗资源 |
| Nanite | **开** | 几何体优化 |
| TSR (Temporal Super Resolution) | **开** | 提升帧率 |
| Shadow Quality | **High** | 不需要 Epic |
| Post Process | **Medium** | 降低 GPU 负载 |
| 目标帧率 | **60 FPS** | 稳定即可 |
| GPU 利用率 | **40-60%** | 留有余量 |

```bash
# 运行时性能监控
nvidia-smi dmon -s u -d 5  # 每 5 秒输出 GPU 使用率

# 或使用 UE5 内置统计
# 控制台命令（UE5 ~键）：
stat fps
stat unit
stat gpu
```

---

## 七、OBS 最终合成

### 7.1 macOS OBS 场景配置

创建以下 OBS 场景：

**场景 1：虚拟演播室**（主场景）
```
Sources (从下到上):
1. [Media Source] UE5 渲染输出
   - Input: srt://0.0.0.0:9001 (或 Browser Source for Pixel Streaming)
   - 全屏 1920x1080
2. [Text] 字幕/标题（可选）
   - 底部三分之一
3. [Image] 台标/水印（可选）
   - 右上角，带透明度
```

**场景 2：画中画**
```
Sources:
1. [Media Source] UE5 渲染输出 (全屏)
2. [Window Capture] 特定应用窗口 (右下角小窗)
```

**场景 3：纯桌面**（备用）
```
Sources:
1. [Screen Capture] macOS 桌面
```

### 7.2 源叠加顺序

```
Layer 5 (top):    [Text] 字幕 / Lower Third
Layer 4:          [Image] 台标 / 水印
Layer 3:          [Filter] 颜色校正
Layer 2:          [Media Source] UE5 渲染输出
Layer 1 (bottom): [Color Source] 黑色背景（保底）
```

### 7.3 录制 / 直播推流设置

#### 录制设置
```
Settings → Output → Recording:
- Recording Path: ~/Videos/Studio/
- Recording Format: MKV (后可无损转 MP4)
- Encoder: Apple VT H265 Hardware Encoder (macOS)
- Bitrate: 15000-20000 Kbps (高质量)
- Keyframe Interval: 2s
```

#### 直播推流设置
```
Settings → Stream:
- Service: Custom
- Server: rtmp://your-streaming-server/live
- Stream Key: your_key

Settings → Output → Streaming:
- Encoder: x264 (or Apple VT H264)
- Bitrate: 4500-6000 Kbps
- Keyframe Interval: 2s
- CPU Usage Preset: veryfast (x264)
```

---

## 八、MVP 检查清单

按优先级排列，逐步完成：

### Phase 1：基础环境
- [ ] macOS 安装 UE5（Epic Games Launcher）
- [ ] macOS 安装 OBS Studio
- [ ] Ubuntu 安装 NVIDIA 驱动（nvidia-smi 正常）
- [ ] Ubuntu 安装 Vulkan（vulkaninfo 正常）
- [ ] Ubuntu 配置 X11 桌面环境

### Phase 2：UE5 项目
- [ ] 创建 VirtualStudio UE5 项目
- [ ] 搭建基础场景（桌子 + 显示器 + 落地窗）
- [ ] 配置基础灯光（三点布光）
- [ ] 导入并放置 MetaHuman 角色
- [ ] 设置坐姿 Idle 循环动画

### Phase 3：视频流 + 渲染
- [ ] macOS OBS NDI 输出（或 SRT 推流 → ffmpeg RTSP 桥接）
- [ ] UE5 NDI/RTSP 接收 → 贴到显示器
- [ ] 实现隐私雾化材质（PrivacyLevel 参数）
- [ ] 配置 Pixel Streaming 或 SRT 输出
- [ ] macOS OBS 接收 UE5 渲染输出

### Phase 4：控制系统
- [ ] UE5 HTTP 控制端点（Remote Control API，至少暴露 PrivacyLevel）
- [ ] SceneMind 后端 `/studio` API 路由
- [ ] 前端 `/studio` 控制台页面（MVP：隐私滑块 + 场景切换）
- [ ] 端到端控制闭环验证

### Phase 5：完善
- [ ] 天气/时间系统
- [ ] 多场景预设
- [ ] 角色动画切换
- [ ] 灯光精细调节
- [ ] 状态监控面板
- [ ] OBS 场景切换集成

### Phase 6：部署
- [ ] UE5 项目打包 Linux
- [ ] Ubuntu systemd 服务配置
- [ ] 性能调优（GPU 40-60%）
- [ ] 完整闭环录制测试

---

## 附录

### A. 常用命令速查

```bash
# Ubuntu: 检查 GPU 状态
nvidia-smi

# Ubuntu: 启动/停止虚拟演播室
sudo systemctl start virtual-studio
sudo systemctl stop virtual-studio
journalctl -u virtual-studio -f

# Ubuntu: SRT 测试
srt-live-transmit "srt://0.0.0.0:9000?mode=listener" file://output.ts

# macOS: OBS 日志
cat ~/Library/Application\ Support/obs-studio/logs/$(ls -t ~/Library/Application\ Support/obs-studio/logs/ | head -1)

# UE5 控制台命令
stat fps          # 帧率
stat unit         # 各线程耗时
stat gpu          # GPU 详情
r.ScreenPercentage 100  # 渲染分辨率百分比
```

### B. 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| UE5 渲染黑屏 | 无 X11 DISPLAY | 检查 `echo $DISPLAY`，设置 `:0` |
| SRT 连接失败 | 防火墙 | `sudo ufw allow 9000` (SRT 使用 UDP，但握手需 TCP) |
| MetaHuman 加载慢 | 首次流式下载 | 等待完成，后续会缓存 |
| GPU 利用率 100% | Path Tracing 开启 | 关闭 Path Tracing |
| Pixel Streaming 延迟高 | WebRTC ICE 失败 | 检查网络，使用 STUN 设为局域网 |
| OBS 接收花屏 | SRT latency 过低 | 增加 latency 到 300000+ |
| HTTP 控制无响应 | Remote Control API 未启用 | 检查 UE5 插件列表，确认端口 30010 |

### C. 参考资源

- [UE5 Pixel Streaming 文档](https://docs.unrealengine.com/5.4/en-US/pixel-streaming-in-unreal-engine/)
- [MetaHuman 文档](https://docs.unrealengine.com/5.4/en-US/metahuman-documentation/)
- [SRT 协议规范](https://github.com/Haivision/srt)
- [OBS SRT 指南](https://obsproject.com/wiki/Streaming-With-SRT-Protocol)
- [UE5 Remote Control API](https://docs.unrealengine.com/5.4/en-US/remote-control-api-for-unreal-engine/)
- [UE5 Media Framework](https://docs.unrealengine.com/5.4/en-US/media-framework-in-unreal-engine/)
- [NDI SDK / UE5 NDI Plugin](https://ndi.video/tools/unreal-engine/)

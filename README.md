# Krita_SpaceMouse_Plugin
3DConnecion SpaceMouse Support For  Krita 

用 3Dconnexion SpaceMouse 控制 Krita 画布的**平移、缩放、旋转**。
## 声明
我并不会编写插件,所有内容使用DeepSeek生成.目的是可以用3DSpaceMouse提高绘画效率.


## ✨ 功能

- 🖐️ 左右推 → 画布水平平移
- 🔍 前后推 → 画布缩放
- ↕️ 上下推 → 画布垂直平移
- 🔄 拧动 → 画布旋转

所有轴的灵敏度和功能都可以在设置里调整。

## 📋 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 (64位) |
| Krita | 5.x |
| 驱动 | 3Dconnexion 3DxWare |
| Python | 3.13 (根据你的Krita版本，仅安装时需要) |

## 🚀 安装

1. 安装 [3DxWare 驱动](https://3dconnexion.com/software/3dxware/)
2. 安装 pynavlib(注意使用对应Krita的Python版本)：
   ```powershell
   py -3.13 -m pip install pynavlib --target="$env:APPDATA\krita\pykrita"

3. 把 spacemouse_krita.desktop 和 spacemouse_krita\ 复制到
%APPDATA%\krita\pykrita\

4. 重启 Krita 并启用插件
## 🚀 使用方法
1. `设置` → `配置 Krita` → `Python 插件管理器` → 勾选 **SpaceMouse Krita**
2. 再次重启 Krita
3. 菜单 `工具` → `脚本` → `启用/停止 SpaceMouse`

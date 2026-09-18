# Android 壳工程

这个目录只是把 `web/` 里的网页版课表包成一个安装包（WebView 壳），页面逻辑完全复用网页版。

构建由 `.github/workflows/android.yml` 在 GitHub Actions 上完成，本地不需要装 Android SDK：

1. 先把 `web/` 的内容复制到 `app/src/main/assets/www/`（CI 会自动做这一步，本地构建时也需手动复制）；
2. 在 `android/` 目录执行 `gradle assembleRelease`；
3. 产物在 `app/build/outputs/apk/release/app-release.apk`。

App 内的数据策略：优先联网从 GitHub Pages 拉最新加密课表，失败则使用打包进 App 的那一份。

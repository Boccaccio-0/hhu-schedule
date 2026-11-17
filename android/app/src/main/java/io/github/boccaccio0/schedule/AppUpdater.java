package io.github.boccaccio0.schedule;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import javax.net.ssl.HttpsURLConnection;

/** 用户主动检查，下载交给浏览器，安装及签名校验交给 Android。 */
final class AppUpdater {
    private final Activity activity;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private AlertDialog dialog;
    private Future<?> request;
    private int generation;
    private boolean closed;

    AppUpdater(Activity activity) {
        this.activity = activity;
    }

    void check() {
        cancelCheck();
        final int checkId = generation;
        dialog = new AlertDialog.Builder(activity)
                .setTitle("检查应用更新")
                .setMessage("当前版本：" + BuildConfig.VERSION_NAME + "\n正在连接 GitHub…")
                .setNegativeButton("取消", (d, which) -> cancelCheck())
                .setOnCancelListener(d -> cancelCheck())
                .show();
        request = executor.submit(() -> {
            try {
                UpdateInfo info = UpdateInfo.parse(fetchMetadata());
                activity.runOnUiThread(() -> {
                    if (!isActive(checkId)) return;
                    dialog.dismiss();
                    AlertDialog.Builder result = new AlertDialog.Builder(activity);
                    if (info.isNewerThan(BuildConfig.VERSION_CODE)) {
                        result.setTitle("发现新版本 " + info.versionName)
                                .setMessage("当前版本：" + BuildConfig.VERSION_NAME
                                        + "\n将打开浏览器下载安装包。下载完成后，点开文件按系统提示安装。覆盖安装会保留本机时间安排。")
                                .setPositiveButton("下载更新", (d, which) -> openBrowser(UpdateInfo.APK_URL + "?v=" + info.versionCode))
                                .setNegativeButton("稍后", null);
                    } else {
                        result.setTitle("已是最新版本")
                                .setMessage("当前版本：" + BuildConfig.VERSION_NAME + "\n课表内容可在设置中单独同步。")
                                .setPositiveButton("知道了", null);
                    }
                    dialog = result.show();
                });
            } catch (Exception error) {
                activity.runOnUiThread(() -> {
                    if (!isActive(checkId)) return;
                    dialog.dismiss();
                    dialog = new AlertDialog.Builder(activity)
                            .setTitle("暂时无法检查更新")
                            .setMessage("请检查网络后重试。也可以打开 GitHub 下载页手动下载，当前数据不受影响。")
                            .setPositiveButton("重试", (d, which) -> check())
                            .setNeutralButton("打开下载页", (d, which) -> openBrowser(UpdateInfo.RELEASE_URL))
                            .setNegativeButton("取消", null)
                            .show();
                });
            }
        });
    }

    private static String fetchMetadata() throws IOException {
        // 直接读取发布附件，不消耗 GitHub API 的匿名访问额度。
        HttpsURLConnection connection = (HttpsURLConnection) new URL(
                UpdateInfo.METADATA_URL + "?t=" + System.currentTimeMillis()).openConnection();
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(10000);
        connection.setUseCaches(false);
        connection.setRequestProperty("User-Agent", "HHUSchedule/" + BuildConfig.VERSION_NAME);
        try {
            if (connection.getResponseCode() != 200) throw new IOException("Update unavailable");
            try (InputStream input = connection.getInputStream();
                 ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[4096];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (Thread.currentThread().isInterrupted()) throw new IOException("Cancelled");
                    if (output.size() + count > 16384) throw new IOException("Metadata too large");
                    output.write(buffer, 0, count);
                }
                return new String(output.toByteArray(), StandardCharsets.UTF_8);
            }
        } finally {
            connection.disconnect();
        }
    }

    private boolean isActive(int checkId) {
        return !closed && !activity.isFinishing() && !activity.isDestroyed() && checkId == generation;
    }

    private void cancelCheck() {
        generation++;
        if (request != null) request.cancel(true);
        if (dialog != null) dialog.dismiss();
    }

    private void openBrowser(String url) {
        try {
            activity.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (ActivityNotFoundException error) {
            Toast.makeText(activity, "请先安装浏览器，再重试下载更新", Toast.LENGTH_LONG).show();
        }
    }

    void close() {
        closed = true;
        cancelCheck();
        executor.shutdownNow();
    }
}

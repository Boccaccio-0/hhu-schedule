package io.github.boccaccio0.schedule;

import org.json.JSONException;
import org.json.JSONObject;

/** 与安装包一起生成的公开版本信息，不包含口令或用户数据。 */
final class UpdateInfo {
    static final String RELEASE_URL = "https://github.com/Boccaccio-0/hhu-schedule/releases/tag/apk";
    static final String APK_URL = "https://github.com/Boccaccio-0/hhu-schedule/releases/download/apk/hhu-schedule.apk";
    static final String METADATA_URL = "https://github.com/Boccaccio-0/hhu-schedule/releases/download/apk/update.json";

    final int versionCode;
    final String versionName;

    private UpdateInfo(int versionCode, String versionName) {
        this.versionCode = versionCode;
        this.versionName = versionName;
    }

    static UpdateInfo parse(String text) throws JSONException {
        JSONObject json = new JSONObject(text);
        Object code = json.get("versionCode");
        String name = json.getString("versionName");
        if (!(code instanceof Integer) || (Integer) code <= 0
                || !name.matches("[0-9]+(?:\\.[0-9]+){1,3}")
                || !APK_URL.equals(json.getString("apkUrl"))) {
            throw new JSONException("Invalid update metadata");
        }
        return new UpdateInfo((Integer) code, name);
    }

    boolean isNewerThan(int installedVersion) {
        return versionCode > installedVersion;
    }
}

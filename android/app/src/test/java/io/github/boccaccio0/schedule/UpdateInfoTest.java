package io.github.boccaccio0.schedule;

import org.json.JSONException;
import org.junit.Test;

import static org.junit.Assert.*;

public class UpdateInfoTest {
    private static String metadata(String code, String name, String url) {
        return "{\"versionCode\":" + code + ",\"versionName\":\"" + name
                + "\",\"apkUrl\":\"" + url + "\"}";
    }

    @Test public void newerReleaseOffersUpdate() throws Exception {
        UpdateInfo info = UpdateInfo.parse(metadata("4", "1.3", UpdateInfo.APK_URL));
        assertTrue(info.isNewerThan(3));
        assertEquals("1.3", info.versionName);
    }

    @Test public void equalOrOlderReleaseNeverDowngrades() throws Exception {
        UpdateInfo info = UpdateInfo.parse(metadata("3", "1.2", UpdateInfo.APK_URL));
        assertFalse(info.isNewerThan(3));
        assertFalse(info.isNewerThan(4));
    }

    @Test public void comparesNumericCodesNotNames() throws Exception {
        assertTrue(UpdateInfo.parse(metadata("10", "1.10", UpdateInfo.APK_URL)).isNewerThan(9));
    }

    @Test public void rejectsInvalidVersionCodes() {
        for (String code : new String[]{"0", "-1", "3.5", "\"4\"", "null", "2147483648"}) {
            assertThrows(JSONException.class, () -> UpdateInfo.parse(metadata(code, "1.2", UpdateInfo.APK_URL)));
        }
    }

    @Test public void rejectsUntrustedDownloadUrls() {
        for (String url : new String[]{"https://example.com/app.apk", UpdateInfo.APK_URL + ".evil", "http://github.com/app.apk", ""}) {
            assertThrows(JSONException.class, () -> UpdateInfo.parse(metadata("4", "1.3", url)));
        }
    }

    @Test public void rejectsIncompleteOrMalformedMetadata() {
        for (String text : new String[]{"", "not json", "{}", "[]", "{\"versionCode\":4}"}) {
            assertThrows(JSONException.class, () -> UpdateInfo.parse(text));
        }
    }

    @Test public void rejectsInvalidDisplayVersion() {
        for (String name : new String[]{"", "4", "new version", "1.2<script>"}) {
            assertThrows(JSONException.class, () -> UpdateInfo.parse(metadata("4", name, UpdateInfo.APK_URL)));
        }
    }
}

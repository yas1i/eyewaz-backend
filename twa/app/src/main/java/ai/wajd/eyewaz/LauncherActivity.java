/*
 * Copyright 2020 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package ai.wajd.eyewaz;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Toast;

public class LauncherActivity
        extends com.google.androidbrowserhelper.trusted.LauncherActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // No orientation lock: Android 16 ignores it on large screens and Play flags it.
        try {
            super.onCreate(savedInstanceState);
        } catch (ActivityNotFoundException e) {
            // Device has no browser able to host the app (disabled or missing Chrome).
            // Try any VIEW handler, then give up politely instead of crashing.
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(getString(R.string.launchUrl))));
            } catch (ActivityNotFoundException ignored) {
                Toast.makeText(this, "EYEWAZ needs a web browser. Please install or enable Chrome.",
                        Toast.LENGTH_LONG).show();
            }
            finish();
        }
    }

    @Override
    protected Uri getLaunchingUrl() {
        return super.getLaunchingUrl();
    }
}

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

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;

import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.google.androidbrowserhelper.trusted.WebViewFallbackActivity;

public class Application extends android.app.Application {

  private static final int BAR_COLOUR = Color.parseColor("#1F3D3A");

  @Override
  public void onCreate() {
      super.onCreate();
      // The library's WebView fallback draws edge to edge (forced on Android 15+) and does not
      // handle insets, so its page header sits under the status bar. Pad it by the system bars.
      registerActivityLifecycleCallbacks(new ActivityLifecycleCallbacks() {
          @Override
          public void onActivityCreated(Activity activity, Bundle state) {
              if (!(activity instanceof WebViewFallbackActivity)) return;
              View content = activity.findViewById(android.R.id.content);
              content.setBackgroundColor(BAR_COLOUR);
              ViewCompat.setOnApplyWindowInsetsListener(content, (v, windowInsets) -> {
                  Insets bars = windowInsets.getInsets(
                          WindowInsetsCompat.Type.systemBars()
                                  | WindowInsetsCompat.Type.displayCutout()
                                  | WindowInsetsCompat.Type.ime());
                  v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                  return WindowInsetsCompat.CONSUMED;
              });
              ViewCompat.requestApplyInsets(content);
          }
          @Override public void onActivityStarted(Activity a) {}
          @Override public void onActivityResumed(Activity a) {}
          @Override public void onActivityPaused(Activity a) {}
          @Override public void onActivityStopped(Activity a) {}
          @Override public void onActivitySaveInstanceState(Activity a, Bundle b) {}
          @Override public void onActivityDestroyed(Activity a) {}
      });
  }
}

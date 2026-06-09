plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "ai.wajd.eyewaztts"
    compileSdk = 34

    defaultConfig {
        applicationId = "ai.wajd.eyewaztts"
        minSdk = 21
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // Uses only the Android framework (TextToSpeechService, HttpURLConnection,
    // org.json) — no third-party libraries needed.
}

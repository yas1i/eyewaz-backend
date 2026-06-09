import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Secrets stay OUT of source control. Put your real values in
// android-tts/secrets.properties (gitignored); see secrets.properties.example.
val secrets = Properties().apply {
    val f = rootProject.file("secrets.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
fun secret(key: String, default: String) =
    (secrets.getProperty(key) ?: System.getenv(key) ?: default)

android {
    namespace = "ai.wajd.eyewaztts"
    compileSdk = 34

    defaultConfig {
        applicationId = "ai.wajd.eyewaztts"
        minSdk = 21
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        buildConfigField("String", "TTS_URL",
            "\"${secret("TTS_URL", "http://10.0.2.2:8090/tts")}\"")
        buildConfigField("String", "TTS_API_KEY",
            "\"${secret("TTS_API_KEY", "")}\"")
    }

    buildFeatures {
        buildConfig = true
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

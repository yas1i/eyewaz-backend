package ai.wajd.eyewaztts

/**
 * Connection to YOUR self-hosted EYEWAZ TTS engine (tts-service).
 *
 * Values come from BuildConfig, which is populated from the gitignored
 * android-tts/secrets.properties at build time (see secrets.properties.example).
 * Nothing secret lives in source control.
 *
 * For production use an HTTPS URL (Caddy) and remove usesCleartextTraffic.
 */
object Config {
    const val TTS_URL = BuildConfig.TTS_URL
    const val API_KEY = BuildConfig.TTS_API_KEY
}

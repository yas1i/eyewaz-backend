package ai.wajd.eyewaztts

import android.media.AudioFormat
import android.speech.tts.SynthesisCallback
import android.speech.tts.SynthesisRequest
import android.speech.tts.TextToSpeech
import android.speech.tts.TextToSpeechService
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * System text-to-speech engine. Android (and any app, including TalkBack) calls
 * onSynthesizeText(); we POST the text to the EYEWAZ TTS server, get a WAV back,
 * and stream its PCM samples to the framework.
 */
class EyewazTtsService : TextToSpeechService() {

    @Volatile private var stopRequested = false

    private fun isUrdu(lang: String?): Boolean {
        val l = lang?.lowercase() ?: return false
        return l == "urd" || l == "ur"
    }

    override fun onIsLanguageAvailable(lang: String?, country: String?, variant: String?): Int =
        if (isUrdu(lang)) TextToSpeech.LANG_AVAILABLE else TextToSpeech.LANG_NOT_SUPPORTED

    override fun onLoadLanguage(lang: String?, country: String?, variant: String?): Int =
        onIsLanguageAvailable(lang, country, variant)

    override fun onGetLanguage(): Array<String> = arrayOf("urd", "PAK", "")

    override fun onStop() {
        stopRequested = true
    }

    override fun onSynthesizeText(request: SynthesisRequest, callback: SynthesisCallback) {
        stopRequested = false
        val text = request.charSequenceText?.toString()?.trim().orEmpty()
        if (text.isEmpty()) { callback.done(); return }
        try {
            val wav = fetchWav(text) ?: run { callback.error(); return }
            val pcm = parseWav(wav) ?: run { callback.error(); return }
            callback.start(pcm.sampleRate, AudioFormat.ENCODING_PCM_16BIT, pcm.channels)
            val data = pcm.data
            val maxBuf = callback.maxBufferSize
            var off = 0
            while (off < data.size) {
                if (stopRequested) { callback.done(); return }
                val len = minOf(maxBuf, data.size - off)
                if (callback.audioAvailable(data, off, len) == TextToSpeech.ERROR) return
                off += len
            }
            callback.done()
        } catch (e: Exception) {
            callback.error()
        }
    }

    private fun fetchWav(text: String): ByteArray? {
        val conn = (URL(Config.TTS_URL).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 10_000
            readTimeout = 60_000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Accept", "audio/wav")
            if (Config.API_KEY.isNotEmpty()) setRequestProperty("X-API-Key", Config.API_KEY)
        }
        try {
            val body = JSONObject().put("text", text).toString().toByteArray(Charsets.UTF_8)
            conn.outputStream.use { it.write(body) }
            if (conn.responseCode != 200) return null
            val out = ByteArrayOutputStream()
            conn.inputStream.use { it.copyTo(out) }
            return out.toByteArray()
        } finally {
            conn.disconnect()
        }
    }

    private data class Pcm(val data: ByteArray, val sampleRate: Int, val channels: Int)

    /** Minimal WAV parser: find fmt + data chunks (PCM 16-bit). */
    private fun parseWav(wav: ByteArray): Pcm? {
        if (wav.size < 44 || String(wav, 0, 4, Charsets.US_ASCII) != "RIFF") return null
        val bb = ByteBuffer.wrap(wav).order(ByteOrder.LITTLE_ENDIAN)
        var pos = 12
        var sampleRate = 16000
        var channels = 1
        var dataOffset = -1
        var dataLen = 0
        while (pos + 8 <= wav.size) {
            val id = String(wav, pos, 4, Charsets.US_ASCII)
            val size = bb.getInt(pos + 4)
            val body = pos + 8
            when (id) {
                "fmt " -> {
                    channels = bb.getShort(body + 2).toInt()
                    sampleRate = bb.getInt(body + 4)
                }
                "data" -> { dataOffset = body; dataLen = size }
            }
            if (dataOffset >= 0) break
            pos = body + size + (size and 1) // chunks are word-aligned
        }
        if (dataOffset < 0) return null
        val end = minOf(dataOffset + dataLen, wav.size)
        return Pcm(wav.copyOfRange(dataOffset, end), sampleRate, if (channels < 1) 1 else channels)
    }
}

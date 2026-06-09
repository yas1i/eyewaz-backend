package ai.wajd.eyewaztts

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.widget.Button
import android.widget.Toast
import java.util.Locale

/** Launcher screen: test the EYEWAZ voice, and open Android's TTS settings. */
class MainActivity : Activity() {

    private var tts: TextToSpeech? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        findViewById<Button>(R.id.testVoice).setOnClickListener { testVoice() }

        findViewById<Button>(R.id.openSettings).setOnClickListener {
            try {
                startActivity(Intent("com.android.settings.TTS_SETTINGS"))
            } catch (e: Exception) {
                startActivity(Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }
    }

    /** Speak a sample through THIS engine specifically (even if not the default). */
    private fun testVoice() {
        Toast.makeText(this, "Connecting to the EYEWAZ voice…", Toast.LENGTH_SHORT).show()
        tts?.shutdown()
        tts = TextToSpeech(this, TextToSpeech.OnInitListener { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale("ur")
                tts?.speak(
                    "السلام علیکم، یہ ای ویواز کی اردو آواز ہے۔ پڑھنا مشکل ہے، سننا آسان ہے۔",
                    TextToSpeech.QUEUE_FLUSH, null, "eyewaz-test"
                )
            } else {
                runOnUiThread {
                    Toast.makeText(this, "Could not start the EYEWAZ engine.", Toast.LENGTH_LONG).show()
                }
            }
        }, "ai.wajd.eyewaztts")  // bind to our engine explicitly
    }

    override fun onDestroy() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        super.onDestroy()
    }
}

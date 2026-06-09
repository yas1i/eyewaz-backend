package ai.wajd.eyewaztts

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.speech.tts.TextToSpeech

/** Returns the sample sentence for the "Listen to an example" button in Settings. */
class GetSampleTextActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val result = Intent().apply {
            putExtra(TextToSpeech.Engine.EXTRA_SAMPLE_TEXT,
                "السلام علیکم، یہ ای ویواز کی اردو آواز ہے۔")
        }
        setResult(TextToSpeech.LANG_AVAILABLE, result)
        finish()
    }
}

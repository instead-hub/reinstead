package ru.hugeping.reinstead;

import org.libsdl.app.SDLActivity;
import android.content.res.AssetManager;
import java.io.IOException;
import java.io.File;
import android.util.Log;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import java.util.Locale;
//import android.view.accessibility.AccessibilityManager;

public class reinsteadActivity extends SDLActivity
{
	TextToSpeech tts;
	boolean ttsInitialized;
	boolean ttsStarted;
	String ttsCached;
	@Override
	protected void onCreate(Bundle savedInstanceState) {
		AssetManager asset_manager = getApplicationContext().getAssets();
		try {
			String path = Assets.copyDirorfileFromAssetManager(asset_manager, "data", getFilesDir() + "/");
			Assets.copyAssetFile(asset_manager, "data/stamp", getFilesDir() + "/stamp");
			Log.v("reinstead", path);
		} catch(IOException e) {
			// Nom nom
			Log.v("reinstead", "Can't copy assets");
		}
		super.onCreate(savedInstanceState);
	}

	public void onDestroy(){
		if (tts !=null)
			tts.shutdown();
		super.onDestroy();
	}

	public void onPause(){
		if(tts !=null){
			tts.stop();
		}
		super.onPause();
	}
}

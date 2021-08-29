package ru.hugeping.reinstead;

import org.libsdl.app.SDLActivity;
import android.content.res.AssetManager;
import java.io.IOException;
import java.io.File;
import android.util.Log;
import android.os.Bundle;

public class reinsteadActivity extends SDLActivity
{
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        AssetManager asset_manager = getApplicationContext().getAssets();
        try {
    	    String path = Assets.copyDirorfileFromAssetManager(asset_manager, "data", getFilesDir() + "/");
    	    Log.v("reinstead", path);
	} catch(IOException e) {
            // Nom nom
            Log.v("reinstead", "Can't copy assets");
	}    
        super.onCreate(savedInstanceState);
    }
}

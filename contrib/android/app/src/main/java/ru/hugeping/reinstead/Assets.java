package ru.hugeping.reinstead;

import java.io.IOException;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.io.InputStream;
import java.io.File;
import java.io.FileReader;
import java.io.InputStreamReader;
import java.io.BufferedReader;
import android.os.Environment;
import android.content.Context;
import android.content.res.AssetManager;
import android.util.Log;

public class Assets
{
	public static String copyDirorfileFromAssetManager(AssetManager asset_manager,
							   String arg_assetDir,
							   String arg_destinationDir) throws IOException
	{
		String dest_dir_path = arg_destinationDir;
		Log.e("reinstead", "External: " + dest_dir_path);
		File dest_dir = new File(dest_dir_path);
		boolean doCopy = true;
		try {
			BufferedReader reader = new BufferedReader(new FileReader(dest_dir_path + "/stamp"));
			String line1 = reader.readLine();
			Log.e("reinstead", "Internal stamp: " + line1);
			BufferedReader reader2 = new BufferedReader(new InputStreamReader(asset_manager.open(arg_assetDir + "/stamp")));
			String line2 = reader2.readLine();
			Log.e("reinstead", "Assets stamp: " + line2);
			doCopy = !line2.equals(line1);
		} catch (IOException io) {}

		if (!doCopy)
			return dest_dir_path;

		createDir(dest_dir);

		String[] files = asset_manager.list(arg_assetDir);

		for (int i = 0; i < files.length; i++) {
			String abs_asset_file_path = addTrailingSlash(arg_assetDir) + files[i];
			String sub_files[] = asset_manager.list(abs_asset_file_path);
			if (sub_files.length == 0) {
				// It is a file
				String dest_file_path = addTrailingSlash(dest_dir_path) + files[i];
				if (!abs_asset_file_path.equals(arg_assetDir + "/stamp"))
					copyAssetFile(asset_manager, abs_asset_file_path, dest_file_path);
			} else {
				// It is a sub directory
				copyDirorfileFromAssetManager(asset_manager, abs_asset_file_path,
							      addTrailingSlash(arg_destinationDir) + files[i]);
			}
		}
		return dest_dir_path;
	}


	public static void copyAssetFile(AssetManager asset_manager, String assetFilePath,
					 String destinationFilePath) throws IOException
	{
		InputStream in = asset_manager.open(assetFilePath);
		OutputStream out = new FileOutputStream(destinationFilePath);

		byte[] buf = new byte[1024];
		int len;
		while ((len = in.read(buf)) > 0)
			out.write(buf, 0, len);
		in.close();
		out.close();
	}

	public static String addTrailingSlash(String path)
	{
		if (path.charAt(path.length() - 1) != '/')
			path += "/";
		return path;
	}

	public static String addLeadingSlash(String path)
	{
		if (path.charAt(0) != '/')
			path = "/" + path;
		return path;
	}

	public static void createDir(File dir) throws IOException
	{
		if (dir.exists()) {
			if (!dir.isDirectory())
				throw new IOException("Can't create directory, a file is in the way");
		} else {
			dir.mkdirs();
			if (!dir.isDirectory())
				throw new IOException("Unable to create directory");

		}
	}
}

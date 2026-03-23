# Phase 2: Frontend Setup & Integration Guide (Android / Kotlin)

This document outlines the steps required for the Frontend Team to integrate the TFLite anomaly detection model into the Asfalis Android application.

## 📦 Files for Handover
The following files must be provided to the Frontend Team from the backend training pipeline (located in `data_visualisation/output_images`):

1. **`auto_sos_mobile.tflite`**: The compiled, quantized TensorFlow Lite model.
2. **`model_metadata.json`**: Documentation of the model's required input/output shapes (`[1, 17]`), feature sequence, and the standard scaler means/scales required to normalize real-time Android data before prediction.

---

## 🛠 Step-by-Step Implementation Guide

### Step 1: Add TensorFlow Lite Dependencies
Open your `app/build.gradle.kts` file and add the required TensorFlow Lite dependencies to the `dependencies` block:

```kotlin
dependencies {
    // Other dependencies...
    
    // TensorFlow Lite for mobile inference
    implementation("org.tensorflow:tensorflow-lite:2.14.0")
    implementation("org.tensorflow:tensorflow-lite-support:0.4.4")
}
```

### Step 2: Package the Model Asset
1. In Android Studio, ensure you have an `assets` directory. If not, right-click the `app/src/main` directory -> **New** -> **Folder** -> **Assets Folder**.
2. Copy the `auto_sos_mobile.tflite` file into the `app/src/main/assets/` directory.

### Step 3: Disable Compression for `.tflite` Files
Android aggressively compresses assets by default, which corrupts memory-mapped TFLite models. You must explicitly disable compression for `.tflite` extensions.

Add this under the `android {}` block in `app/build.gradle.kts`:

```kotlin
android {
    // ...
    
    // Disable compression for TFLite models
    aaptOptions {
        noCompress("tflite")
    }
}
```

*Note: If using newer Android Gradle Plugin versions, the syntax in `build.gradle.kts` is:*
```kotlin
android {
    androidResources {
        noCompress.add("tflite")
    }
}
```

### Step 4: Normalizing Real-Time Sensor Data
Before passing data into the `.tflite` model, the frontend must extract the 17 features from a 300-point window (roughly 6 seconds of 50Hz data) and scale them using `StandardScaler`.

Look inside the provided `model_metadata.json`. It contains a `normalization` block with arrays for `mean` and `scale`. 
For every feature $x$, apply the standard scaler formula:
`x_scaled = (x - mean) / scale`

### Step 5: Run Inference in Kotlin
Create an `Interpreter` instance and pass the normalized `[1, 17]` `FloatArray` to get the inference probability.

```kotlin
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.channels.FileChannel
import android.content.res.AssetManager

class SOSDetector(assetManager: AssetManager) {

    private var interpreter: Interpreter

    init {
        val model = loadModelFile(assetManager, "auto_sos_mobile.tflite")
        interpreter = Interpreter(model)
    }

    private fun loadModelFile(assetManager: AssetManager, modelPath: String): java.nio.MappedByteBuffer {
        val fileDescriptor = assetManager.openFd(modelPath)
        val inputStream = FileInputStream(fileDescriptor.fileDescriptor)
        val fileChannel = inputStream.channel
        return fileChannel.map(
            FileChannel.MapMode.READ_ONLY,
            fileDescriptor.startOffset,
            fileDescriptor.declaredLength
        )
    }

    fun predictDanger(features: FloatArray): Float {
        // features must be size 17 and pre-scaled
        val input = arrayOf(features) // Shape: [1, 17]
        val output = arrayOf(FloatArray(1)) // Shape: [1, 1]

        interpreter.run(input, output)
        
        // Return probability
        return output[0][0]
    }
}
```

### Step 6: Trigger the SOS (Threshold Logic)
The `predictDanger` function will return a probability between `0.0` and `1.0`. 
Check `model_metadata.json` for the `recommended_threshold` (e.g., `0.60`).
If the prediction is `>= 0.60`, trigger the application's SOS sequence.

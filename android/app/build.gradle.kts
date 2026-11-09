import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// Gleiche Versionsnummer wie die Desktop-App (pyproject.toml) – ein Release, eine Nummer.
val desktopVersion: String = rootProject.file("../pyproject.toml").readLines()
    .first { it.startsWith("version") }.substringAfter('"').substringBefore('"')
val versionParts = desktopVersion.split('.').map { it.toInt() }

// Öffentliche Release-Schlüssel für den Updater – aus derselben Datei wie am Desktop (src/tunebridge/release_signers)
val releaseKeys: String = rootProject.file("../src/tunebridge/release_signers").readLines()
    .filter { !it.startsWith("#") && "sh-tunebridge-release" in it && "ssh-ed25519" in it }
    .map { it.substringAfter("ssh-ed25519").trim().split(Regex("\\s+"))[0] }
    .joinToString(",")

// Release-Schlüssel liegt nie im Repo: keystore.properties (storeFile, keyAlias) – die Passwörter kommen nur beim Bauen
// über TB_STORE_PASSWORD / TB_KEY_PASSWORD (scripts/publish-android.sh fragt sie ab), nie als Datei.
val keystoreProps = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "de.bs002.tunebridge"
    compileSdk = 36
    buildToolsVersion = "36.0.0"

    defaultConfig {
        applicationId = "de.bs002.tunebridge"
        minSdk = 29
        targetSdk = 36
        versionName = desktopVersion
        versionCode = versionParts[0] * 10000 + versionParts[1] * 100 + versionParts[2]
        resourceConfigurations += listOf("de")
        buildConfigField("String", "RELEASE_KEYS", "\"$releaseKeys\"")
        buildConfigField("String", "UPDATE_REPO", "\"Bigsmoke002/SH-Tunebridge\"")
    }

    signingConfigs {
        if (keystoreProps.isNotEmpty()) {
            create("release") {
                storeFile = rootProject.file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword") ?: System.getenv("TB_STORE_PASSWORD")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword") ?: System.getenv("TB_KEY_PASSWORD") ?: System.getenv("TB_STORE_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".dev"
            versionNameSuffix = "-dev"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources.excludes += listOf("/META-INF/{AL2.0,LGPL2.1}", "/META-INF/*.kotlin_module", "DebugProbesKt.bin")
    }
    dependenciesInfo {
        // Kein von Google verschlüsselter Abhängigkeits-Block im APK (nur für den Play Store gedacht)
        includeInApk = false
        includeInBundle = false
    }
}

kotlin {
    compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.splash)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime)
    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.androidx.lifecycle.process)
    implementation(libs.androidx.navigation.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.foundation)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.camera.camera2)
    implementation(libs.camera.lifecycle)
    implementation(libs.camera.view)
    implementation(libs.zxing.core)
    implementation(libs.bouncycastle)          // nur Ed25519-Prüfung der Update-Signatur (MIT)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp)
    implementation(libs.coil.compose)
    testImplementation(libs.junit)
}

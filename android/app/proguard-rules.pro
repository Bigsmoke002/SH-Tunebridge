# kotlinx.serialization: erzeugte Serializer behalten
-keepattributes *Annotation*, InnerClasses
-keepclassmembers class de.bs002.tunebridge.** {
    *** Companion;
}
-keepclasseswithmembers class de.bs002.tunebridge.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

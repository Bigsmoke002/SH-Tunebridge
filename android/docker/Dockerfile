# Build-Umgebung für die Android-App. Das Android-SDK liegt nur in diesem Container – nichts davon im System.
#   docker build -t tunebridge-android android/docker
#   scripts/android-build.sh
FROM eclipse-temurin:21-jdk

ARG CMDLINE_TOOLS=13114758
ARG GRADLE=8.14.3
ENV ANDROID_HOME=/opt/android-sdk \
    GRADLE_HOME=/opt/gradle \
    GRADLE_USER_HOME=/cache/gradle
ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$GRADLE_HOME/bin

RUN apt-get update && apt-get install -y --no-install-recommends unzip ca-certificates curl && rm -rf /var/lib/apt/lists/*

RUN mkdir -p $ANDROID_HOME/cmdline-tools \
 && curl -fsSL -o /tmp/tools.zip https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS}_latest.zip \
 && unzip -q /tmp/tools.zip -d /tmp/tools && mv /tmp/tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest && rm -rf /tmp/tools*

RUN yes | sdkmanager --licenses > /dev/null \
 && sdkmanager "platforms;android-36" "build-tools;36.0.0" > /dev/null

RUN curl -fsSL -o /tmp/gradle.zip https://services.gradle.org/distributions/gradle-${GRADLE}-bin.zip \
 && unzip -q /tmp/gradle.zip -d /opt && mv /opt/gradle-${GRADLE} $GRADLE_HOME && rm /tmp/gradle.zip

WORKDIR /src/android

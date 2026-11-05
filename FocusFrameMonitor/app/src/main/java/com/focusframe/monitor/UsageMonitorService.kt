package com.focusframe.monitor

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder

import com.google.firebase.database.FirebaseDatabase


class UsageMonitorService : Service() {

    // =========================================================
    // STUDENT INFORMATION
    // =========================================================

    private var studentId = ""


    // =========================================================
    // TEACHER SESSION STATE
    // =========================================================

    private var teacherSessionActive = false

    private var activeSessionId = ""


    // =========================================================
    // SESSION TRACKING — focus score accumulators
    // =========================================================

    /** Epoch ms when service was created — used for session duration. */
    private var sessionStartTime: Long = 0L

    /** Accumulated usage seconds per category for the current session. */
    private var educationalSeconds: Long    = 0L
    private var nonEducationalSeconds: Long = 0L
    private var neutralSeconds: Long        = 0L


    // =========================================================
    // BACKGROUND THREAD FOR MONITORING LOOPS
    // =========================================================

    /** Dedicated background thread — keeps monitoring off the UI thread. */
    private val handlerThread =
        android.os.HandlerThread("FocusFrameMonitorThread").also { it.start() }

    private val handler =
        android.os.Handler(handlerThread.looper)


    // =========================================================
    // CURRENT APP TRACKING
    // =========================================================

    private var lastPackage = ""

    private var lastAppStartTime: Long = 0L
    // Guard to avoid clearing interval state before async Firebase write completes
    private var flushingInterval = false

    /**
     * Flush the currently tracked foreground interval, if any, to Firebase.
     *
     * The flush occurs only when a non‑blank `activeSessionId` is present,
     * `lastPackage` is not empty, and a start time has been recorded.
     * It also guards against negative or zero durations.
     * After a successful write the tracking fields are cleared so the
     * method is idempotent.
     */
    private fun closeCurrentIntervalIfOpen(targetSessionId: String = "") {
        val targetSession = if (targetSessionId.isNotBlank()) targetSessionId else activeSessionId
        // Guard against trying to write when no session is active or a write is already pending.
        if (targetSession.isBlank() || lastPackage.isEmpty() || lastAppStartTime <= 0L || flushingInterval) {
            return
        }

        // Capture current interval data immutably
        val pkg = lastPackage
        val start = lastAppStartTime
        val currentTime = System.currentTimeMillis()

        // Prevent pre-session usage from leaking into classroom duration
        val effectiveStart = if (sessionStartTime > 0L && start < sessionStartTime) sessionStartTime else start
        var durationMs = currentTime - effectiveStart
        if (durationMs < 0) durationMs = 0
        val durationSec = durationMs / 1000L

        // Clear tracking state for the completed interval
        lastPackage = ""
        lastAppStartTime = 0L
        flushingInterval = false

        if (durationSec <= 0L) {
            return
        }

        // Persist using the captured package, duration, and target session
        accumulateDuration(pkg, durationSec)
        saveDetectedApp(targetSession, pkg, durationSec)
    }


    // =========================================================
    // MONITORING LOOP
    // =========================================================

    private val monitorRunnable =
        object : Runnable {

            override fun run() {

                if (teacherSessionActive) {
                    detectApp()
                }

                handler.postDelayed(
                    this,
                    2000
                )
            }
        }


    // =========================================================
    // CHECK TEACHER SESSION
    // =========================================================

    private val teacherSessionRunnable =
        object : Runnable {

            override fun run() {

                checkTeacherSession()

                handler.postDelayed(
                    this,
                    5000
                )
            }
        }


    // =========================================================
    // SERVICE CREATED
    // =========================================================

    override fun onCreate() {

        // -----------------------------------------------------
        // Record session start time
        // -----------------------------------------------------

        sessionStartTime = System.currentTimeMillis()


        // -----------------------------------------------------
        // Get paired student ID
        // -----------------------------------------------------

        studentId =
            getSharedPreferences(
                "FocusFrameUsage",
                Context.MODE_PRIVATE
            ).getString(
                "student_id",
                ""
            ) ?: ""


        super.onCreate()


        // -----------------------------------------------------
        // Create notification channel
        // -----------------------------------------------------

        createNotificationChannel()


        // -----------------------------------------------------
        // Create foreground notification
        // -----------------------------------------------------

        val notification =
            createNotification(
                "Waiting for teacher session"
            )


        // -----------------------------------------------------
        // Start foreground service
        // -----------------------------------------------------

        if (
            Build.VERSION.SDK_INT >=
            Build.VERSION_CODES.Q
        ) {

            startForeground(
                1001,
                notification,
                android.content.pm.ServiceInfo
                    .FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )

        } else {

            startForeground(
                1001,
                notification
            )
        }


        // -----------------------------------------------------
        // Follow teacher-controlled classroom sessions
        // -----------------------------------------------------

        handler.post(
            teacherSessionRunnable
        )

        handler.post(
            monitorRunnable
        )
    }


    // =========================================================
    // CHECK WHETHER TEACHER HAS AN ACTIVE CLASSROOM SESSION
    // =========================================================

    private fun checkTeacherSession() {

        // This method runs on the dedicated handler thread (same as monitorRunnable).
        // All mutable state accessed here is therefore confined to that thread,
        // but we still synchronize when we might be re‑entered from onDestroy.
        synchronized(this) {
        FirebaseDatabase.getInstance()
            .getReference("classroom_sessions")
            .get()
            .addOnSuccessListener { snapshot ->

                    var newestSessionId: String? = null
                    var newestCreatedAt = ""

                    for (session in snapshot.children) {
                        val active = session.child("active").getValue(Boolean::class.java)
                        if (active != true) continue

                        val createdAt = session.child("created_at").getValue(String::class.java) ?: ""
                        if (newestSessionId == null || createdAt > newestCreatedAt) {
                            newestSessionId = session.key
                            newestCreatedAt = createdAt
                        }
                    }

                    val newSessionId = newestSessionId ?: ""

                    // -----------------------------------------------------------------
                    // CASE ANALYSIS
                    // -----------------------------------------------------------------
                    // Case A: No previous active session (activeSessionId blank) -> start new session.
                    // Case B: Switching from one non‑blank session to another non‑blank session.
                    // Case C: Switching from a non‑blank session to no session (blank).
                    // Case D: Session unchanged – do nothing.

                    if (newSessionId != activeSessionId) {
                        val oldSessionId = activeSessionId

                        // Flush any pending interval that belongs to the *old* session.
                        if (oldSessionId.isNotBlank()) {
                            closeCurrentIntervalIfOpen(oldSessionId)
                            educationalSeconds = 0L
                            nonEducationalSeconds = 0L
                            neutralSeconds = 0L
                        }

                        // Switch to the new session ID (may be blank).
                        activeSessionId = newSessionId

                        // If we have entered a fresh non‑blank session, initialise its clock.
                        if (newSessionId.isNotBlank()) {
                            val now = System.currentTimeMillis()
                            sessionStartTime = now
                            // If an app is already in the foreground, anchor tracking from session start
                            if (lastPackage.isNotEmpty()) {
                                lastAppStartTime = now
                            }
                        } else {
                            sessionStartTime = 0L
                            lastPackage = ""
                            lastAppStartTime = 0L
                        }
                    }

                    // Update UI state flags.
                    teacherSessionActive = newSessionId.isNotBlank()

                    // Persist flags for the ViewModel.
                    getSharedPreferences(
                        "FocusFrameUsage",
                        Context.MODE_PRIVATE
                    )
                        .edit()
                        .putBoolean(
                            "monitoring_active",
                            teacherSessionActive
                        )
                        .putString(
                            "active_session_id",
                            activeSessionId
                        )
                        .apply()

                    // Update notification.
                    updateNotification(
                        if (teacherSessionActive) "Classroom monitoring active" else "Waiting for teacher session"
                    )
                }
                .addOnFailureListener {
                    // If we cannot read sessions, stop monitoring.
                    teacherSessionActive = false
                    getSharedPreferences(
                        "FocusFrameUsage",
                        Context.MODE_PRIVATE
                    )
                        .edit()
                        .putBoolean(
                            "monitoring_active",
                            false
                        )
                        .apply()
                    updateNotification("Waiting for teacher session")
                }
        }
}


/*
            FirebaseDatabase.getInstance()

        database
            .getReference("classroom_sessions")
            .get()
            .addOnSuccessListener { snapshot ->

                var newestSessionId: String? = null
                var newestCreatedAt = ""

                for (session in snapshot.children) {

                    val active =
                        session
                            .child("active")
                            .getValue(Boolean::class.java)

                    if (active != true) {
                        continue
                    }

                    val createdAt =
                        session
                            .child("created_at")
                            .getValue(String::class.java)
                            ?: ""

                    if (
                        newestSessionId == null ||
                        createdAt > newestCreatedAt
                    ) {
                        newestSessionId = session.key
                        newestCreatedAt = createdAt
                    }
                }

                val newSessionId =
                    newestSessionId ?: ""

                if (newSessionId != activeSessionId) {

                    lastPackage = ""

                    lastAppStartTime = 0L

                    activeSessionId =
                        newSessionId
                }

                teacherSessionActive =
                    newSessionId.isNotBlank()

                getSharedPreferences(
                    "FocusFrameUsage",
                    Context.MODE_PRIVATE
                )
                    .edit()
                    .putBoolean(
                        "monitoring_active",
                        teacherSessionActive
                    )
                    .putString(
                        "active_session_id",
                        activeSessionId
                    )
                    .apply()

                updateNotification(
                    if (teacherSessionActive)
                        "Classroom monitoring active"
                    else
                        "Waiting for teacher session"
                )
            }
            .addOnFailureListener {

                teacherSessionActive = false

                getSharedPreferences(
                    "FocusFrameUsage",
                    Context.MODE_PRIVATE
                )
                    .edit()
                    .putBoolean(
                        "monitoring_active",
                        false
                    )
                    .apply()

                updateNotification(
                    "Waiting for teacher session"
                )
*/



    // =========================================================
    // DETECT CURRENT APP
    // =========================================================

    private fun detectApp() {

        val usageStatsManager =
            getSystemService(
                Context.USAGE_STATS_SERVICE
            ) as UsageStatsManager


        // -----------------------------------------------------
        // Check recent usage events
        // -----------------------------------------------------

        val endTime =
            System.currentTimeMillis()

        val startTime =
            endTime - 10_000


        val usageEvents =
            usageStatsManager.queryEvents(
                startTime,
                endTime
            )


        val event =
            UsageEvents.Event()


        var newestPackage = ""

        var newestEventTime = 0L


        // -----------------------------------------------------
        // Find newest resumed application
        // -----------------------------------------------------

        while (
            usageEvents.hasNextEvent()
        ) {

            usageEvents.getNextEvent(
                event
            )


            if (
                event.eventType ==
                UsageEvents.Event.ACTIVITY_RESUMED
            ) {

                val packageName =
                    event.packageName


                // -------------------------------------------------
                // Ignore FocusFrame itself
                // -------------------------------------------------

                if (
                    packageName !=
                    packageNameOfApp()
                ) {

                    if (
                        event.timeStamp >=
                        newestEventTime
                    ) {

                        newestEventTime =
                            event.timeStamp

                        newestPackage =
                            packageName
                    }
                }
            }
        }


        // -----------------------------------------------------
        // Ignore launcher/system UI
        // -----------------------------------------------------

        if (
            newestPackage.isEmpty()
        ) {
            return
        }


        if (
            newestPackage ==
            "com.android.systemui"
        ) {
            return
        }


        if (
            newestPackage ==
            "com.miui.home"
        ) {
            return
        }


        // -----------------------------------------------------
        // Process only when app changes
        // -----------------------------------------------------

        if (
            newestPackage !=
            lastPackage
        ) {

            val currentTime =
                System.currentTimeMillis()


            // -------------------------------------------------
            // Save previous application's duration
            // -------------------------------------------------

            if (
                lastPackage.isNotEmpty() &&
                lastAppStartTime > 0L
            ) {

                // ---------------------------------------------
                // currentTime and lastAppStartTime are in
                // milliseconds.
                //
                // Convert milliseconds to seconds before
                // sending the value to Firebase.
                // ---------------------------------------------

                val durationMilliseconds =
                    currentTime -
                            lastAppStartTime

                val durationSeconds =
                    durationMilliseconds / 1000L


                // ---------------------------------------------
                // Accumulate session totals by category
                // ---------------------------------------------

                accumulateDuration(
                    lastPackage,
                    durationSeconds
                )


                saveDetectedApp(
                    lastPackage,
                    durationSeconds
                )
            }


            // -------------------------------------------------
            // Start tracking new application
            // -------------------------------------------------

            lastPackage =
                newestPackage

            lastAppStartTime =
                currentTime
        }
    }


    // =========================================================
    // ACCUMULATE DURATION BY CATEGORY & UPDATE FOCUS SUMMARY
    // =========================================================

    /**
     * Adds [durationSeconds] to the appropriate per-session accumulator,
     * then recomputes the focus score and writes it to SharedPreferences
     * (for the ViewModel to pick up) and to Firebase.
     */
    private fun accumulateDuration(
        packageName: String,
        durationSeconds: Long
    ) {

        // -----------------------------------------------------
        // Classify and accumulate
        // -----------------------------------------------------

        val classification =
            try {
                AppClassifier.classify(packageName)
            } catch (e: Exception) {
                ClassificationResult(category = "Unknown", confidence = 0.50)
            }

        val latestCategory = classification.category

        when (latestCategory) {
            "Educational"     -> educationalSeconds    += durationSeconds
            "Non-Educational" -> nonEducationalSeconds += durationSeconds
            "Neutral"         -> neutralSeconds        += durationSeconds
            else              -> nonEducationalSeconds += durationSeconds   // Unknown → conservative
        }


        // -----------------------------------------------------
        // Compute focus score
        // -----------------------------------------------------

        val totalActiveSeconds =
            educationalSeconds + nonEducationalSeconds

        val focusScore: Int =
            if (totalActiveSeconds == 0L) {
                100     // No distractions detected yet
            } else {
                ((educationalSeconds.toDouble() / totalActiveSeconds) * 100)
                    .toInt()
                    .coerceIn(0, 100)
            }


        // -----------------------------------------------------
        // Convert seconds → minutes for display
        // -----------------------------------------------------

        val eduMinutes    = educationalSeconds    / 60L
        val nonEduMinutes = nonEducationalSeconds / 60L
        val neutralMins   = neutralSeconds        / 60L

        val sessionDurationMinutes =
            (System.currentTimeMillis() - sessionStartTime) / 60_000L


        // -----------------------------------------------------
        // Write focus summary to SharedPreferences
        // (ViewModel polling loop reads these every 1 s)
        // -----------------------------------------------------

        getSharedPreferences(
            "FocusFrameUsage",
            Context.MODE_PRIVATE
        )
            .edit()
            .putInt(MainViewModel.PREF_FOCUS_SCORE,      focusScore)
            .putLong(MainViewModel.PREF_EDU_MINUTES,     eduMinutes)
            .putLong(MainViewModel.PREF_NON_EDU_MINUTES, nonEduMinutes)
            .putLong(MainViewModel.PREF_NEUTRAL_MINUTES, neutralMins)
            .putLong(MainViewModel.PREF_SESSION_DURATION, sessionDurationMinutes)
            .putString(MainViewModel.PREF_LATEST_CATEGORY, latestCategory)
            .apply()


        // -----------------------------------------------------
        // Write focus summary to Firebase
        // phone_usage/{sessionId}/focus_summary/{studentId}
        // -----------------------------------------------------

        if (activeSessionId.isNotBlank() && studentId.isNotBlank()) {

            val focusSummaryData = mapOf<String, Any>(
                "focus_score"              to focusScore,
                "educational_minutes"      to eduMinutes,
                "non_educational_minutes"  to nonEduMinutes,
                "neutral_minutes"          to neutralMins,
                "session_duration_minutes" to sessionDurationMinutes,
                "last_updated"             to System.currentTimeMillis()
            )

            FirebaseDatabase.getInstance()
                .getReference("phone_usage")
                .child(activeSessionId)
                .child("focus_summary")
                .child(studentId)
                .setValue(focusSummaryData)
        }
    }


    // =========================================================
    // GET FOCUSFRAME PACKAGE NAME
    // =========================================================

    private fun packageNameOfApp(): String {

        return applicationContext.packageName
    }


    // =========================================================
    // SAVE DETECTED APP LOCALLY + FIREBASE
    // =========================================================

    private fun saveDetectedApp(
        packageName: String,
        duration: Long
    ) {

        val prefs =
            getSharedPreferences(
                "FocusFrameUsage",
                Context.MODE_PRIVATE
            )


        // -----------------------------------------------------
        // Get application name
        // -----------------------------------------------------

        val appName =
            try {

                val appInfo =
                    packageManager.getApplicationInfo(
                        packageName,
                        0
                    )


                packageManager
                    .getApplicationLabel(
                        appInfo
                    )
                    .toString()

            } catch (
                e: Exception
            ) {

                packageName
            }


        // -----------------------------------------------------
        // Current time
        // -----------------------------------------------------

        val time =
            java.text.SimpleDateFormat(
                "HH:mm:ss",
                java.util.Locale.getDefault()
            ).format(
                java.util.Date()
            )


        // -----------------------------------------------------
        // Local history record
        // -----------------------------------------------------

        val record =
            "$time - $appName ($packageName)"


        val oldHistory =
            prefs.getString(
                "history",
                ""
            ) ?: ""


        val historyLines =
            oldHistory
                .split("\n")
                .filter {
                    it.isNotBlank()
                }
                .toMutableList()


        historyLines.add(
            record
        )


        // -----------------------------------------------------
        // Keep latest 20 records
        // -----------------------------------------------------

        while (
            historyLines.size > 20
        ) {

            historyLines.removeAt(0)
        }


        val newHistory =
            historyLines.joinToString(
                "\n"
            )


        // -----------------------------------------------------
        // Save local information
        // -----------------------------------------------------

        prefs.edit()
            .putString(
                "latest_app",
                appName
            )
            .putString(
                "latest_package",
                packageName
            )
            .putString(
                "latest_time",
                time
            )
            .putString(
                "history",
                newHistory
            )
            .apply()


        // -----------------------------------------------------
        // Classify application
        // -----------------------------------------------------

        val classification =
            try {

                AppClassifier.classify(
                    packageName
                )

            } catch (
                e: Exception
            ) {

                ClassificationResult(
                    category = "Unknown",
                    confidence = 0.50
                )
            }


        // -----------------------------------------------------
        // Save usage to Firebase
        // -----------------------------------------------------

        saveUsageToFirebase(
            appName = appName,
            packageName = packageName,
            category = classification.category,
            confidence = classification.confidence,
            duration = duration
        )


        // -----------------------------------------------------
        // Update notification
        // -----------------------------------------------------

        updateNotification(
            "Detected: $appName"
        )
    }


    // =========================================================
    // SAVE USAGE DATA TO FIREBASE
    // =========================================================

    private fun saveUsageToFirebase(
        appName: String,
        packageName: String,
        category: String,
        confidence: Double,
        duration: Long
    ) {

        // -----------------------------------------------------
        // Student ID is required
        // -----------------------------------------------------

        if (
            studentId.isBlank()
        ) {
            return
        }


        val database =
            FirebaseDatabase.getInstance()


        val sessionsRef =
            database.getReference(
                "classroom_sessions"
            )


        // -----------------------------------------------------
        // Read classroom sessions
        // -----------------------------------------------------

        sessionsRef.get()
            .addOnSuccessListener { snapshot ->

                var activeSessionId:
                        String? = null

                var latestCreatedAt =
                    ""


                // -------------------------------------------------
                // Find the newest ACTIVE classroom session
                // -------------------------------------------------

                for (
                session in snapshot.children
                ) {

                    val active =
                        session
                            .child("active")
                            .getValue(
                                Boolean::class.java
                            )


                    if (
                        active != true
                    ) {
                        continue
                    }


                    val createdAt =
                        session
                            .child("created_at")
                            .getValue(
                                String::class.java
                            )
                            ?: ""


                    // ---------------------------------------------
                    // Select the newest active session
                    // ---------------------------------------------

                    if (
                        activeSessionId == null ||
                        createdAt > latestCreatedAt
                    ) {

                        activeSessionId =
                            session.key

                        latestCreatedAt =
                            createdAt
                    }
                }


                // -------------------------------------------------
                // No active classroom session
                // -------------------------------------------------

                if (
                    activeSessionId == null
                ) {

                    return@addOnSuccessListener
                }


                // -------------------------------------------------
                // Firebase phone usage location
                // -------------------------------------------------

                val usageRef =
                    database
                        .getReference(
                            "phone_usage"
                        )
                        .child(
                            activeSessionId!!
                        )


                // -------------------------------------------------
                // Usage data
                // -------------------------------------------------

                val usageData =
                    mapOf(

                        "student_id" to
                                studentId,

                        "app_name" to
                                appName,

                        "package_name" to
                                packageName,

                        "category" to
                                category,

                        "confidence" to
                                confidence,

                        // Duration is now stored in SECONDS
                        "duration" to
                                duration,

                        "timestamp" to
                                System.currentTimeMillis()
                    )


                // -------------------------------------------------
                // Push usage record
                // -------------------------------------------------

                usageRef
                    .push()
                    .setValue(
                        usageData
                    )
                    .addOnFailureListener { e ->
                        android.util.Log.e("UsageMonitor", "Failed to write usage record", e)
                    }
            }

            .addOnFailureListener {

                // -------------------------------------------------
                // Firebase failure does not stop local monitoring
                // -------------------------------------------------

            }
    }


    // =========================================================
    // CREATE NOTIFICATION CHANNEL
    // =========================================================

    private fun createNotificationChannel() {

        // minSdk = 26 (Oreo), so notification channels are always available.
        val channel =
            NotificationChannel(
                "focusframe_monitor",
                "FocusFrame Monitoring",
                NotificationManager.IMPORTANCE_LOW
            )

        getSystemService(NotificationManager::class.java)
            .createNotificationChannel(channel)
    }


    // =========================================================
    // CREATE NOTIFICATION
    // =========================================================

    private fun createNotification(
        text: String
    ): Notification {

        // minSdk = 26 (Oreo), so notification channels are always available.
        return Notification.Builder(
            this,
            "focusframe_monitor"
        )
            .setContentTitle(
                "FocusFrame Monitor"
            )
            .setContentText(
                text
            )
            .setSmallIcon(
                android.R.drawable.ic_menu_view
            )
            .setOngoing(
                true
            )
            .build()
    }


    // =========================================================
    // UPDATE NOTIFICATION
    // =========================================================

    private fun updateNotification(
        text: String
    ) {

        val manager =
            getSystemService(
                NotificationManager::class.java
            )


        manager.notify(
            1001,
            createNotification(
                text
            )
        )
    }


    // =========================================================
    // SERVICE DESTROYED
    // =========================================================

    override fun onDestroy() {
        // Ensure no further callbacks are posted.
        handler.removeCallbacks(monitorRunnable)
        handler.removeCallbacks(teacherSessionRunnable)

        // Best‑effort finalisation of any open interval belonging to the current session.
        synchronized(this) {
            if (teacherSessionActive && activeSessionId.isNotBlank()) {
                closeCurrentIntervalIfOpen()
            }
        }

        // Shut down background thread.
        handlerThread.quitSafely()

        // Clear persisted monitoring flag.
        getSharedPreferences(
            "FocusFrameUsage",
            Context.MODE_PRIVATE
        )
            .edit()
            .putBoolean(
                "monitoring_active",
                false
            )
            .apply()

        super.onDestroy()
    }




    // =========================================================
    // SERVICE BINDING
    // =========================================================

    override fun onBind(
        intent: Intent?
    ): IBinder? {

        return null
    }
}

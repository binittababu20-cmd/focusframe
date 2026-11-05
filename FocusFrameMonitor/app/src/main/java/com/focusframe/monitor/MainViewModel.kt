package com.focusframe.monitor

import android.app.AppOpsManager
import android.app.Application
import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import android.provider.Settings

import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope

import com.google.firebase.database.FirebaseDatabase

import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch


class MainViewModel(application: Application) : AndroidViewModel(application) {

    // =========================================================
    // SHARED PREFERENCES
    // =========================================================

    private val prefs: SharedPreferences =
        application.getSharedPreferences(
            "FocusFrameUsage",
            Context.MODE_PRIVATE
        )

    // SharedPreferences key constants for focus summary
    companion object {
        const val PREF_FOCUS_SCORE       = "focus_score"
        const val PREF_EDU_MINUTES       = "edu_minutes"
        const val PREF_NON_EDU_MINUTES   = "non_edu_minutes"
        const val PREF_NEUTRAL_MINUTES   = "neutral_minutes"
        const val PREF_SESSION_DURATION  = "session_duration_minutes"
        const val PREF_LATEST_CATEGORY   = "latest_app_category"
    }


    // =========================================================
    // UI STATE
    // =========================================================

    private val _uiState = MutableStateFlow(loadStateFromPrefs())

    /** The single source of truth consumed by [MainScreen]. */
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    /**
     * One-shot event emitted after a successful pairing so [MainActivity]
     * can start the foreground service without the ViewModel holding a
     * reference to the [android.content.Context].
     */
    private val _startServiceEvent = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val startServiceEvent: SharedFlow<Unit> = _startServiceEvent.asSharedFlow()


    // =========================================================
    // INIT — start polling loop for live service state
    // =========================================================

    init {
        // Check permissions on startup
        checkPermissions(application)

        viewModelScope.launch {
            while (true) {
                _uiState.update { current ->
                    current.copy(
                        isMonitoring          = prefs.getBoolean("monitoring_active", false),
                        latestApp             = prefs.getString("latest_app", "Not detected") ?: "Not detected",
                        latestPackage         = prefs.getString("latest_package", "") ?: "",
                        latestTime            = prefs.getString("latest_time", "") ?: "",
                        history               = prefs.getString("history", "No usage recorded yet.") ?: "No usage recorded yet.",

                        // ── Focus Score fields ──────────────────────
                        focusScore            = prefs.getInt(PREF_FOCUS_SCORE, 0),
                        educationalMinutes    = prefs.getLong(PREF_EDU_MINUTES, 0L),
                        nonEducationalMinutes = prefs.getLong(PREF_NON_EDU_MINUTES, 0L),
                        neutralMinutes        = prefs.getLong(PREF_NEUTRAL_MINUTES, 0L),
                        sessionDurationMinutes = prefs.getLong(PREF_SESSION_DURATION, 0L),
                        latestAppCategory     = prefs.getString(PREF_LATEST_CATEGORY, "") ?: "",
                        focusLevel            = focusLevelFromScore(prefs.getInt(PREF_FOCUS_SCORE, 0),
                                                                    prefs.getLong(PREF_EDU_MINUTES, 0L) + prefs.getLong(PREF_NON_EDU_MINUTES, 0L))
                    )
                }
                delay(1_000)
            }
        }
    }


    // =========================================================
    // FOCUS LEVEL HELPER
    // =========================================================

    /**
     * Maps a raw focus score to a human-readable focus level label.
     *
     * @param score         0-100 focus score
     * @param totalActive   total active (edu + non-edu) minutes; 0 means no data yet
     */
    private fun focusLevelFromScore(score: Int, totalActive: Long): String =
        when {
            totalActive == 0L -> "No Data"
            score >= 70       -> "High Focus"
            score >= 40       -> "Medium Focus"
            else              -> "Low Focus"
        }


    // =========================================================
    // PAIRING CODE INPUT
    // =========================================================

    fun onPairingCodeChanged(code: String) {
        _uiState.update { it.copy(pairingCode = code.uppercase()) }
    }


    // =========================================================
    // PAIR DEVICE
    // =========================================================

    fun pairDevice() {

        val code = _uiState.value.pairingCode.trim().uppercase()

        if (code.isBlank()) {
            _uiState.update { it.copy(pairingMessage = "Please enter the pairing code.") }
            return
        }

        _uiState.update { it.copy(isPairing = true, pairingMessage = "") }


        // -----------------------------------------------------
        // Look up the pairing code in Firebase
        // -----------------------------------------------------

        FirebaseDatabase.getInstance()
            .getReference("devices")
            .orderByChild("pairing_code")
            .equalTo(code)
            .get()
            .addOnSuccessListener { snapshot ->

                if (!snapshot.exists()) {
                    _uiState.update {
                        it.copy(isPairing = false, pairingMessage = "Invalid pairing code.")
                    }
                    return@addOnSuccessListener
                }


                // -------------------------------------------------
                // Get matching device snapshot
                // -------------------------------------------------

                val deviceSnapshot = snapshot.children.firstOrNull()

                if (deviceSnapshot == null) {
                    _uiState.update {
                        it.copy(isPairing = false, pairingMessage = "Device record not found.")
                    }
                    return@addOnSuccessListener
                }


                // -------------------------------------------------
                // Read student / register number
                // -------------------------------------------------

                val matchedStudentId =
                    deviceSnapshot
                        .child("register_number")
                        .getValue(String::class.java) ?: ""

                if (matchedStudentId.isBlank()) {
                    _uiState.update {
                        it.copy(
                            isPairing = false,
                            pairingMessage = "Student ID not found for this device."
                        )
                    }
                    return@addOnSuccessListener
                }


                // -------------------------------------------------
                // Android device ID
                // -------------------------------------------------

                val androidDeviceId =
                    Settings.Secure.getString(
                        getApplication<Application>().contentResolver,
                        Settings.Secure.ANDROID_ID
                    ) ?: ""


                // -------------------------------------------------
                // Update Firebase device record
                // -------------------------------------------------

                val updates = mapOf<String, Any>(
                    "pairing_status"    to "Paired",
                    "android_device_id" to androidDeviceId,
                    "paired_at"         to System.currentTimeMillis()
                )

                deviceSnapshot.ref.updateChildren(updates)
                    .addOnSuccessListener {

                        // -----------------------------------------
                        // Persist pairing info locally
                        // -----------------------------------------

                        prefs.edit()
                            .putString("student_id",        matchedStudentId)
                            .putString("pairing_code",      code)
                            .putString("pairing_status",    "Paired")
                            .putString("android_device_id", androidDeviceId)
                            .apply()

                        _uiState.update {
                            it.copy(
                                isPairing      = false,
                                studentId      = matchedStudentId,
                                pairingStatus  = "Paired",
                                pairingMessage = "Device paired successfully! Student ID: $matchedStudentId"
                            )
                        }

                        // Signal Activity to start the foreground service
                        _startServiceEvent.tryEmit(Unit)
                    }
                    .addOnFailureListener { error ->
                        _uiState.update {
                            it.copy(
                                isPairing      = false,
                                pairingMessage = "Pairing failed: ${error.message}"
                            )
                        }
                    }
            }
            .addOnFailureListener { error ->
                _uiState.update {
                    it.copy(
                        isPairing      = false,
                        pairingMessage = "Unable to connect to Firebase: ${error.message}"
                    )
                }
            }
    }


    // =========================================================
    // UNPAIR DEVICE
    // =========================================================

    fun unpairDevice() {

        val deviceId =
            prefs.getString("android_device_id", "") ?: ""

        _uiState.update { it.copy(isPairing = true, pairingMessage = "") }


        // -----------------------------------------------------
        // Update Firebase pairing status to "unpaired"
        // -----------------------------------------------------

        if (deviceId.isNotBlank()) {

            FirebaseDatabase.getInstance()
                .getReference("devices")
                .orderByChild("android_device_id")
                .equalTo(deviceId)
                .get()
                .addOnSuccessListener { snapshot ->

                    for (deviceSnapshot in snapshot.children) {
                        deviceSnapshot.ref.updateChildren(
                            mapOf("pairing_status" to "unpaired")
                        )
                    }
                }
        }


        // -----------------------------------------------------
        // Clear all local prefs regardless of Firebase result
        // -----------------------------------------------------

        prefs.edit()
            .remove("student_id")
            .remove("pairing_code")
            .remove("pairing_status")
            .remove("android_device_id")
            .remove("monitoring_active")
            .remove(PREF_FOCUS_SCORE)
            .remove(PREF_EDU_MINUTES)
            .remove(PREF_NON_EDU_MINUTES)
            .remove(PREF_NEUTRAL_MINUTES)
            .remove(PREF_SESSION_DURATION)
            .remove(PREF_LATEST_CATEGORY)
            .apply()

        _uiState.update {
            UiState(
                hasUsagePermission       = it.hasUsagePermission,
                hasNotificationPermission = it.hasNotificationPermission,
                pairingMessage           = "Device unpaired."
            )
        }
    }


    // =========================================================
    // PERMISSION CHECKS
    // =========================================================

    /**
     * Checks runtime permissions and updates [UiState] accordingly.
     * Safe to call from any thread (posts to Main via StateFlow).
     */
    fun checkPermissions(context: Context) {

        // ── Usage Stats permission ────────────────────────────
        val appOps =
            context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager

        @Suppress("DEPRECATION")
        val usageGranted =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                appOps.unsafeCheckOpNoThrow(
                    AppOpsManager.OPSTR_GET_USAGE_STATS,
                    android.os.Process.myUid(),
                    context.packageName
                ) == AppOpsManager.MODE_ALLOWED
            } else {
                appOps.checkOpNoThrow(
                    AppOpsManager.OPSTR_GET_USAGE_STATS,
                    android.os.Process.myUid(),
                    context.packageName
                ) == AppOpsManager.MODE_ALLOWED
            }


        // ── POST_NOTIFICATIONS permission (Android 13+) ───────
        val notifGranted =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                ContextCompat.checkSelfPermission(
                    context,
                    android.Manifest.permission.POST_NOTIFICATIONS
                ) == android.content.pm.PackageManager.PERMISSION_GRANTED
            } else {
                true    // Not required before Android 13
            }

        _uiState.update {
            it.copy(
                hasUsagePermission        = usageGranted,
                hasNotificationPermission = notifGranted
            )
        }
    }

    /** Called by [MainActivity.onResume] to refresh permission state. */
    fun refreshPermissions(context: Context) = checkPermissions(context)


    // =========================================================
    // HELPERS
    // =========================================================

    private fun loadStateFromPrefs(): UiState =
        UiState(
            studentId             = prefs.getString("student_id",     "") ?: "",
            pairingStatus         = prefs.getString("pairing_status", "Not Paired") ?: "Not Paired",
            latestApp             = prefs.getString("latest_app",     "Not detected") ?: "Not detected",
            latestPackage         = prefs.getString("latest_package", "") ?: "",
            latestTime            = prefs.getString("latest_time",    "") ?: "",
            history               = prefs.getString("history",        "No usage recorded yet.") ?: "No usage recorded yet.",
            isMonitoring          = prefs.getBoolean("monitoring_active", false),
            focusScore            = prefs.getInt(PREF_FOCUS_SCORE, 0),
            educationalMinutes    = prefs.getLong(PREF_EDU_MINUTES, 0L),
            nonEducationalMinutes = prefs.getLong(PREF_NON_EDU_MINUTES, 0L),
            neutralMinutes        = prefs.getLong(PREF_NEUTRAL_MINUTES, 0L),
            sessionDurationMinutes = prefs.getLong(PREF_SESSION_DURATION, 0L),
            latestAppCategory     = prefs.getString(PREF_LATEST_CATEGORY, "") ?: ""
        )
}

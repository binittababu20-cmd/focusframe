package com.focusframe.monitor

/**
 * Immutable snapshot of all state displayed on the main screen.
 * The ViewModel exposes this as a [kotlinx.coroutines.flow.StateFlow] so that
 * the Compose UI recomposes only when the data actually changes.
 */
data class UiState(

    // ─── Pairing ───────────────────────────────────────────────
    val studentId: String = "",
    val pairingStatus: String = "Not Paired",
    val pairingCode: String = "",
    val pairingMessage: String = "",

    // ─── Latest detected app ───────────────────────────────────
    val latestApp: String = "Not detected",
    val latestPackage: String = "",
    val latestTime: String = "",

    // ─── History ───────────────────────────────────────────────
    val history: String = "No usage recorded yet.",

    // ─── Monitoring ────────────────────────────────────────────
    val isMonitoring: Boolean = false,

    // ─── Loading / pairing progress flag ───────────────────────
    val isPairing: Boolean = false,

    // ─── Focus Score & Session Summary ─────────────────────────
    val focusScore: Int = 0,                  // 0-100
    val focusLevel: String = "–",             // "High Focus", "Medium Focus", "Low Focus", "No Data"
    val educationalMinutes: Long = 0,         // session total (minutes)
    val nonEducationalMinutes: Long = 0,      // session total (minutes)
    val neutralMinutes: Long = 0,             // session total (minutes)
    val latestAppCategory: String = "",       // last classified category
    val sessionDurationMinutes: Long = 0,     // how long monitoring has been running

    // ─── Permissions ───────────────────────────────────────────
    val hasUsagePermission: Boolean = false,
    val hasNotificationPermission: Boolean = false
)

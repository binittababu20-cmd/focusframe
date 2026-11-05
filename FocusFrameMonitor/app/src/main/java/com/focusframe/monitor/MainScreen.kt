package com.focusframe.monitor

import android.content.Intent
import android.os.Build
import android.provider.Settings

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll

import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue

import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

import com.focusframe.monitor.ui.theme.BorderLight
import com.focusframe.monitor.ui.theme.BorderSubtle
import com.focusframe.monitor.ui.theme.CardBgLight
import com.focusframe.monitor.ui.theme.DangerRed
import com.focusframe.monitor.ui.theme.DangerRedLight
import com.focusframe.monitor.ui.theme.DangerRedText
import com.focusframe.monitor.ui.theme.DarkBg
import com.focusframe.monitor.ui.theme.FocusBlue
import com.focusframe.monitor.ui.theme.FocusBlueHover
import com.focusframe.monitor.ui.theme.FocusFrameMonitorTheme
import com.focusframe.monitor.ui.theme.Gold
import com.focusframe.monitor.ui.theme.Navy
import com.focusframe.monitor.ui.theme.PageBgLight
import com.focusframe.monitor.ui.theme.SlateLight
import com.focusframe.monitor.ui.theme.SlateText
import com.focusframe.monitor.ui.theme.SuccessGreen
import com.focusframe.monitor.ui.theme.SuccessGreenLight
import com.focusframe.monitor.ui.theme.SuccessGreenText
import com.focusframe.monitor.ui.theme.WarningGold
import com.focusframe.monitor.ui.theme.WarningGoldLight
import com.focusframe.monitor.ui.theme.WarningGoldText

/**
 * Standard Navigation Tabs for FocusFrame Android Application.
 * Matches FocusFrame Website Navigation Structure:
 * - Focus Score: Displays Focus Score & Telemetry ONLY
 * - Attendance: Displays Attendance & Session Status ONLY
 * - Student Report: Displays Student App Usage & History ONLY
 * - Device & Settings: Displays Device Pairing & Permissions ONLY
 */
enum class MainNavTab(val label: String, val icon: String) {
    FOCUS_SCORE("Focus Score", "🎯"),
    ATTENDANCE("Attendance", "📅"),
    STUDENT_REPORT("Student Report", "📊"),
    DEVICE("Device", "⚙️")
}

@Composable
fun MainScreen(
    viewModel: MainViewModel,
    onRequestNotificationPermission: () -> Unit = {}
) {
    val state by viewModel.uiState.collectAsState()
    var selectedTab by rememberSaveable { mutableStateOf(MainNavTab.FOCUS_SCORE) }

    FocusFrameMonitorTheme {
        Scaffold(
            topBar = {
                // FocusFrame Website Common Header Bar (Sticky blur style with subtle bottom border)
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    shadowElevation = 2.dp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(width = 1.dp, color = MaterialTheme.colorScheme.outline)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 18.dp, vertical = 12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // Brand Logo matching website .header-logo & .logo-icon
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(38.dp)
                                    .clip(RoundedCornerShape(10.dp))
                                    .background(
                                        Brush.linearGradient(
                                            colors = listOf(FocusBlue, FocusBlueHover)
                                        )
                                    ),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = "F",
                                    color = Color.White,
                                    fontSize = 20.sp,
                                    fontWeight = FontWeight.Black
                                )
                            }

                            Column {
                                Text(
                                    text = "FocusFrame",
                                    fontSize = 19.sp,
                                    fontWeight = FontWeight.ExtraBold,
                                    color = MaterialTheme.colorScheme.onSurface,
                                    letterSpacing = (-0.3).sp
                                )
                                Text(
                                    text = "ATTENDANCE & FOCUS INTELLIGENCE",
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold,
                                    letterSpacing = 0.8.sp,
                                    color = SlateText
                                )
                            }
                        }

                        // Live Session Status Badge (Website pill style)
                        val (statusBg, statusBorder, statusText, statusDot, statusLabel) = when {
                            state.isMonitoring -> listOf(
                                SuccessGreenLight,
                                SuccessGreen.copy(alpha = 0.35f),
                                SuccessGreenText,
                                SuccessGreen,
                                "Active"
                            )
                            state.studentId.isNotBlank() -> listOf(
                                WarningGoldLight,
                                WarningGold.copy(alpha = 0.35f),
                                WarningGoldText,
                                WarningGold,
                                "Waiting"
                            )
                            else -> listOf(
                                BorderSubtle,
                                BorderLight,
                                SlateText,
                                SlateLight,
                                "Unpaired"
                            )
                        }

                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                            modifier = Modifier
                                .clip(RoundedCornerShape(50))
                                .background(statusBg as Color)
                                .border(1.dp, statusBorder as Color, RoundedCornerShape(50))
                                .padding(horizontal = 10.dp, vertical = 5.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(7.dp)
                                    .clip(CircleShape)
                                    .background(statusDot as Color)
                            )
                            Text(
                                text = statusLabel as String,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = statusText as Color
                            )
                        }
                    }
                }
            },
            bottomBar = {
                // FocusFrame Website Navigation (Navy container with active blue pill matching website sidebar)
                NavigationBar(
                    containerColor = Navy,
                    tonalElevation = 8.dp
                ) {
                    MainNavTab.values().forEach { tab ->
                        val isSelected = selectedTab == tab
                        NavigationBarItem(
                            selected = isSelected,
                            onClick = { selectedTab = tab },
                            icon = {
                                Text(
                                    text = tab.icon,
                                    fontSize = 18.sp
                                )
                            },
                            label = {
                                Text(
                                    text = tab.label,
                                    fontSize = 11.sp,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                                )
                            },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = Color.White,
                                selectedTextColor = Color.White,
                                unselectedIconColor = SlateLight,
                                unselectedTextColor = SlateLight,
                                indicatorColor = FocusBlue
                            )
                        )
                    }
                }
            }
        ) { paddingValues ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
                    .background(MaterialTheme.colorScheme.background)
            ) {
                when (selectedTab) {
                    MainNavTab.FOCUS_SCORE -> {
                        FocusScoreOnlyScreen(
                            state = state,
                            onNavigateToReport = { selectedTab = MainNavTab.STUDENT_REPORT }
                        )
                    }
                    MainNavTab.ATTENDANCE -> {
                        AttendanceOnlyScreen(
                            state = state,
                            onNavigateToDevice = { selectedTab = MainNavTab.DEVICE }
                        )
                    }
                    MainNavTab.STUDENT_REPORT -> {
                        StudentReportOnlyScreen(
                            state = state
                        )
                    }
                    MainNavTab.DEVICE -> {
                        DeviceSettingsOnlyScreen(
                            state = state,
                            viewModel = viewModel,
                            onRequestNotificationPermission = onRequestNotificationPermission
                        )
                    }
                }
            }
        }
    }
}

// =============================================================================
// TAB 1: FOCUS SCORE ONLY SCREEN (Matches FocusFrame Metric Cards)
// =============================================================================

@Composable
fun FocusScoreOnlyScreen(
    state: UiState,
    onNavigateToReport: () -> Unit
) {
    val scrollState = rememberScrollState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scrollState)
            .padding(18.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Section Header (Website style)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "Focus Score",
                    fontSize = 24.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    text = "Real-time AI Classroom Telemetry",
                    fontSize = 13.sp,
                    color = SlateText
                )
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(FocusBlue.copy(alpha = 0.1f))
                    .border(1.dp, FocusBlue.copy(alpha = 0.25f), RoundedCornerShape(8.dp))
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            ) {
                Text(
                    text = "Active Metric",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = FocusBlue
                )
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        // Focus Score Theme Color mapping matching website states
        val (scoreColor, scoreBgTint, levelBadgeLabel) = when {
            state.focusLevel == "No Data" || state.focusLevel == "–" -> Triple(
                SlateLight,
                BorderSubtle,
                if (state.isMonitoring) "Gathering Data…" else "Session Idle"
            )
            state.focusScore >= 70 -> Triple(
                SuccessGreen,
                SuccessGreenLight,
                "High Focus • Attentive"
            )
            state.focusScore >= 40 -> Triple(
                WarningGold,
                WarningGoldLight,
                "Medium Focus • Moderate"
            )
            else -> Triple(
                DangerRed,
                DangerRedLight,
                "Low Focus • Distracted"
            )
        }

        // Hero Focus Score Card (Website .stat-card styling)
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(22.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "CURRENT SESSION FOCUS",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = 1.sp,
                    color = SlateText
                )

                Spacer(modifier = Modifier.height(16.dp))

                // Circular Score Indicator with concentric border rings
                Box(
                    modifier = Modifier
                        .size(150.dp)
                        .clip(CircleShape)
                        .background(scoreBgTint)
                        .border(4.dp, scoreColor, CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = if (state.focusLevel == "No Data" || state.focusLevel == "–") "–" else "${state.focusScore}%",
                            fontSize = 42.sp,
                            fontWeight = FontWeight.Black,
                            color = scoreColor
                        )
                        Text(
                            text = "out of 100",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium,
                            color = SlateText
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Focus Level Pill Badge
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(20.dp))
                        .background(scoreBgTint)
                        .border(1.dp, scoreColor.copy(alpha = 0.35f), RoundedCornerShape(20.dp))
                        .padding(horizontal = 14.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = levelBadgeLabel,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = scoreColor
                    )
                }

                Spacer(modifier = Modifier.height(20.dp))

                // Category Duration Breakdown (Educational vs Non-Edu vs Neutral)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    FocusCategoryBox(
                        label = "Educational",
                        value = "${state.educationalMinutes}m",
                        color = FocusBlue,
                        bg = FocusBlue.copy(alpha = 0.08f),
                        icon = "📚",
                        modifier = Modifier.weight(1f)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    FocusCategoryBox(
                        label = "Non-Edu",
                        value = "${state.nonEducationalMinutes}m",
                        color = DangerRed,
                        bg = DangerRedLight,
                        icon = "🎮",
                        modifier = Modifier.weight(1f)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    FocusCategoryBox(
                        label = "Neutral",
                        value = "${state.neutralMinutes}m",
                        color = SlateText,
                        bg = BorderSubtle,
                        icon = "⚙️",
                        modifier = Modifier.weight(1f)
                    )
                }

                Spacer(modifier = Modifier.height(18.dp))

                HorizontalDivider(color = MaterialTheme.colorScheme.outline, thickness = 1.dp)

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Session Duration",
                        fontSize = 13.sp,
                        color = SlateText
                    )
                    Text(
                        text = "⏱️ ${state.sessionDurationMinutes} minutes",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Focus Score Intelligence & Tips Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(text = "💡", fontSize = 18.sp)
                    Text(
                        text = "How Focus Score Works",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "FocusFrame calculates your score from active educational applications (Classroom, Docs, Drive, Zoom, Khan Academy) vs non-educational usage. Scores of 70% and above represent High Focus.",
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                    color = SlateText
                )

                Spacer(modifier = Modifier.height(14.dp))

                OutlinedButton(
                    onClick = onNavigateToReport,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = FocusBlue
                    ),
                    border = androidx.compose.foundation.BorderStroke(1.dp, FocusBlue.copy(alpha = 0.5f))
                ) {
                    Text(
                        text = "View Detailed App Usage Report →",
                        fontWeight = FontWeight.Bold,
                        fontSize = 13.sp
                    )
                }
            }
        }
    }
}

@Composable
private fun FocusCategoryBox(
    label: String,
    value: String,
    color: Color,
    bg: Color,
    icon: String,
    modifier: Modifier = Modifier
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(bg)
            .border(1.dp, color.copy(alpha = 0.2f), RoundedCornerShape(12.dp))
            .padding(vertical = 10.dp, horizontal = 6.dp)
    ) {
        Text(text = icon, fontSize = 16.sp)
        Text(
            text = value,
            fontWeight = FontWeight.ExtraBold,
            fontSize = 16.sp,
            color = color,
            modifier = Modifier.padding(top = 2.dp)
        )
        Text(
            text = label,
            fontSize = 11.sp,
            fontWeight = FontWeight.Medium,
            color = SlateText
        )
    }
}

// =============================================================================
// TAB 2: ATTENDANCE ONLY SCREEN
// =============================================================================

@Composable
fun AttendanceOnlyScreen(
    state: UiState,
    onNavigateToDevice: () -> Unit
) {
    val scrollState = rememberScrollState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scrollState)
            .padding(18.dp)
    ) {
        // Section Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "Attendance",
                    fontSize = 24.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    text = "Session Check-In & Participation",
                    fontSize = 13.sp,
                    color = SlateText
                )
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(FocusBlue.copy(alpha = 0.1f))
                    .border(1.dp, FocusBlue.copy(alpha = 0.25f), RoundedCornerShape(8.dp))
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            ) {
                Text(
                    text = "Attendance Status",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = FocusBlue
                )
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        // Session Card (Website card design)
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Classroom Session",
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )

                    val (sessionBadgeBg, sessionBadgeBorder, sessionBadgeText, sessionBadgeLabel) = if (state.isMonitoring) {
                        listOf(SuccessGreenLight, SuccessGreen.copy(alpha = 0.35f), SuccessGreenText, "● Active Session")
                    } else {
                        listOf(WarningGoldLight, WarningGold.copy(alpha = 0.35f), WarningGoldText, "● Waiting for Session")
                    }

                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(20.dp))
                            .background(sessionBadgeBg as Color)
                            .border(1.dp, sessionBadgeBorder as Color, RoundedCornerShape(20.dp))
                            .padding(horizontal = 10.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = sessionBadgeLabel as String,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = sessionBadgeText as Color
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outline, thickness = 1.dp)
                Spacer(modifier = Modifier.height(12.dp))

                InfoRow(label = "Monitoring Status", value = if (state.isMonitoring) "ACTIVE" else "IDLE")
                InfoRow(label = "Paired Student ID", value = if (state.studentId.isNotBlank()) state.studentId else "Not Paired")
                InfoRow(label = "Session Duration", value = "${state.sessionDurationMinutes} min")
                InfoRow(label = "Attendance Telemetry", value = if (state.studentId.isNotBlank()) "Verified Device" else "Pairing Required")
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // QR Check-In Guide Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(text = "📷", fontSize = 18.sp)
                    Text(
                        text = "QR Attendance Check-In",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "When your teacher begins a session, scan the classroom QR code using the web app (Student Dashboard → Scan QR). Your mobile attendance and focus metrics will synchronize automatically.",
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                    color = SlateText
                )

                if (state.studentId.isBlank()) {
                    Spacer(modifier = Modifier.height(14.dp))
                    Button(
                        onClick = onNavigateToDevice,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = FocusBlue,
                            contentColor = Color.White
                        )
                    ) {
                        Text(
                            text = "Pair This Device Now →",
                            fontWeight = FontWeight.Bold,
                            fontSize = 13.sp
                        )
                    }
                }
            }
        }
    }
}

// =============================================================================
// TAB 3: STUDENT REPORT ONLY SCREEN
// =============================================================================

@Composable
fun StudentReportOnlyScreen(
    state: UiState
) {
    val scrollState = rememberScrollState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scrollState)
            .padding(18.dp)
    ) {
        // Section Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "Student Report",
                    fontSize = 24.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    text = "Detailed App Usage & Telemetry History",
                    fontSize = 13.sp,
                    color = SlateText
                )
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(FocusBlue.copy(alpha = 0.1f))
                    .border(1.dp, FocusBlue.copy(alpha = 0.25f), RoundedCornerShape(8.dp))
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            ) {
                Text(
                    text = "Usage Log",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = FocusBlue
                )
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        // Latest Detected App Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(
                    text = "LATEST DETECTED APP",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = 1.sp,
                    color = SlateText
                )

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = state.latestApp,
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Bold,
                    color = FocusBlue
                )

                if (state.latestPackage.isNotEmpty()) {
                    Text(
                        text = state.latestPackage,
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace,
                        color = SlateText,
                        modifier = Modifier.padding(top = 2.dp)
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (state.latestAppCategory.isNotEmpty()) {
                        val (catBg, catBorder, catColor) = when (state.latestAppCategory.lowercase()) {
                            "educational" -> Triple(SuccessGreenLight, SuccessGreen.copy(alpha = 0.35f), SuccessGreenText)
                            "non-educational", "non educational" -> Triple(DangerRedLight, DangerRed.copy(alpha = 0.35f), DangerRedText)
                            else -> Triple(BorderSubtle, BorderLight, SlateText)
                        }

                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(6.dp))
                                .background(catBg)
                                .border(1.dp, catBorder, RoundedCornerShape(6.dp))
                                .padding(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text(
                                text = state.latestAppCategory,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = catColor
                            )
                        }
                    }

                    if (state.latestTime.isNotEmpty()) {
                        Text(
                            text = "⏱️ ${state.latestTime}",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium,
                            color = SlateText
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // History Log Card with Monospace Console Styling
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(
                    text = "Detected Application History",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )

                Spacer(modifier = Modifier.height(12.dp))

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(MaterialTheme.colorScheme.background)
                        .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(12.dp))
                        .padding(14.dp)
                ) {
                    Text(
                        text = state.history,
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace,
                        lineHeight = 18.sp,
                        color = MaterialTheme.colorScheme.onBackground
                    )
                }
            }
        }
    }
}

// =============================================================================
// TAB 4: DEVICE & SETTINGS ONLY SCREEN
// =============================================================================

@Composable
fun DeviceSettingsOnlyScreen(
    state: UiState,
    viewModel: MainViewModel,
    onRequestNotificationPermission: () -> Unit
) {
    val context = LocalContext.current
    val scrollState = rememberScrollState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scrollState)
            .padding(18.dp)
    ) {
        // Section Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "Device & Pairing",
                    fontSize = 24.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    text = "Manage Student Device Connection",
                    fontSize = 13.sp,
                    color = SlateText
                )
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(FocusBlue.copy(alpha = 0.1f))
                    .border(1.dp, FocusBlue.copy(alpha = 0.25f), RoundedCornerShape(8.dp))
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            ) {
                Text(
                    text = "Pairing",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = FocusBlue
                )
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        // Usage Permission Warning if missing (Website Warning styling)
        if (!state.hasUsagePermission) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = DangerRedLight
                ),
                border = androidx.compose.foundation.BorderStroke(1.dp, DangerRed.copy(alpha = 0.4f))
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "⚠️ Usage Access Required",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp,
                        color = DangerRedText
                    )
                    Text(
                        text = "FocusFrame needs Usage Access permission to classify educational vs non-educational apps in real-time.",
                        fontSize = 13.sp,
                        color = DangerRedText,
                        modifier = Modifier.padding(top = 4.dp)
                    )
                    Button(
                        onClick = {
                            context.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
                        },
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = DangerRed,
                            contentColor = Color.White
                        ),
                        modifier = Modifier.padding(top = 10.dp)
                    ) {
                        Text("Grant Usage Access", fontWeight = FontWeight.Bold)
                    }
                }
            }
            Spacer(modifier = Modifier.height(14.dp))
        }

        // Notification Permission Warning if missing
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !state.hasNotificationPermission) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = WarningGoldLight
                ),
                border = androidx.compose.foundation.BorderStroke(1.dp, WarningGold.copy(alpha = 0.4f))
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "🔔 Notification Permission Recommended",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp,
                        color = WarningGoldText
                    )
                    Text(
                        text = "Allow notifications so your session attendance and monitoring status are visible in the Android status bar.",
                        fontSize = 13.sp,
                        color = WarningGoldText,
                        modifier = Modifier.padding(top = 4.dp)
                    )
                    Button(
                        onClick = onRequestNotificationPermission,
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = WarningGold,
                            contentColor = Navy
                        ),
                        modifier = Modifier.padding(top = 10.dp)
                    ) {
                        Text("Allow Notifications", fontWeight = FontWeight.Bold)
                    }
                }
            }
            Spacer(modifier = Modifier.height(14.dp))
        }

        // Device Pairing Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(
                    text = "Pair with Student Account",
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = "Enter the 8-character pairing code displayed on your FocusFrame Student Dashboard.",
                    fontSize = 13.sp,
                    color = SlateText,
                    modifier = Modifier.padding(top = 4.dp)
                )

                Spacer(modifier = Modifier.height(12.dp))

                OutlinedTextField(
                    value = state.pairingCode,
                    onValueChange = viewModel::onPairingCodeChanged,
                    label = { Text("8-Character Pairing Code") },
                    placeholder = { Text("e.g. 8FD60E0C") },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = FocusBlue,
                        focusedLabelColor = FocusBlue,
                        cursorColor = FocusBlue
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(12.dp))

                Button(
                    onClick = viewModel::pairDevice,
                    enabled = state.pairingCode.isNotBlank() && !state.isPairing && state.hasUsagePermission,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = FocusBlue,
                        contentColor = Color.White,
                        disabledContainerColor = FocusBlue.copy(alpha = 0.4f),
                        disabledContentColor = Color.White.copy(alpha = 0.7f)
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    if (state.isPairing) {
                        CircularProgressIndicator(
                            color = Color.White,
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Pairing Device…", fontWeight = FontWeight.Bold)
                    } else {
                        Text("Pair Device", fontWeight = FontWeight.Bold)
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outline, thickness = 1.dp)
                Spacer(modifier = Modifier.height(12.dp))

                InfoRow(
                    label = "Pairing Status",
                    value = if (state.studentId.isNotBlank()) state.pairingStatus else "Not Paired"
                )

                if (state.studentId.isNotBlank()) {
                    InfoRow(label = "Student ID", value = state.studentId)

                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedButton(
                        onClick = viewModel::unpairDevice,
                        enabled = !state.isPairing,
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = DangerRed
                        ),
                        border = androidx.compose.foundation.BorderStroke(1.dp, DangerRed.copy(alpha = 0.5f)),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("Unpair Device", fontWeight = FontWeight.Bold)
                    }
                }

                if (state.pairingMessage.isNotEmpty()) {
                    Text(
                        text = state.pairingMessage,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                        color = FocusBlue,
                        modifier = Modifier.padding(top = 8.dp)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Quick System Settings Link
        OutlinedButton(
            onClick = {
                context.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
            },
            shape = RoundedCornerShape(10.dp),
            colors = ButtonDefaults.outlinedButtonColors(
                contentColor = SlateText
            ),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("⚙️ Open System Usage Access Settings", fontSize = 13.sp)
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            fontSize = 13.sp,
            color = SlateText
        )
        Text(
            text = value,
            fontSize = 13.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}

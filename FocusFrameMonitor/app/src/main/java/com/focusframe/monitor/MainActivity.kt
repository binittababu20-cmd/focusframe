package com.focusframe.monitor

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle

import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle

import kotlinx.coroutines.launch


class MainActivity : ComponentActivity() {

    // =========================================================
    // VIEW MODEL
    // =========================================================

    private val viewModel: MainViewModel by viewModels()


    // =========================================================
    // NOTIFICATION PERMISSION LAUNCHER (Android 13+)
    // =========================================================

    private val requestNotificationPermission =
        registerForActivityResult(
            ActivityResultContracts.RequestPermission()
        ) { _ ->
            // Refresh permission state in ViewModel after user responds
            viewModel.refreshPermissions(this)
        }


    // =========================================================
    // ACTIVITY LIFECYCLE
    // =========================================================

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        enableEdgeToEdge()

        // Start monitoring service if the device is already paired
        startMonitoringServiceIfPaired()

        // Observe one-shot event from ViewModel to start service after pairing
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.startServiceEvent.collect {
                    startMonitoringServiceIfPaired()
                }
            }
        }

        // setContent is called exactly once; all UI state is driven
        // reactively through MainViewModel -> MainScreen.
        setContent {
            MainScreen(
                viewModel = viewModel,
                onRequestNotificationPermission = {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        requestNotificationPermission.launch(
                            android.Manifest.permission.POST_NOTIFICATIONS
                        )
                    }
                }
            )
        }
    }


    // =========================================================
    // REFRESH PERMISSIONS WHEN RETURNING TO THE APP
    // =========================================================

    override fun onResume() {
        super.onResume()
        viewModel.refreshPermissions(this)
    }


    // =========================================================
    // START FOREGROUND MONITORING SERVICE
    // =========================================================

    private fun startMonitoringServiceIfPaired() {

        val studentId =
            getSharedPreferences("FocusFrameUsage", Context.MODE_PRIVATE)
                .getString("student_id", "") ?: ""

        if (studentId.isBlank()) {
            return
        }

        startForegroundService(
            Intent(this, UsageMonitorService::class.java)
        )
    }
}

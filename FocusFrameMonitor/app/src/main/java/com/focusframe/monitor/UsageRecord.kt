package com.focusframe.monitor

import com.google.firebase.database.PropertyName

data class UsageRecord(

    @get:PropertyName("app_name")
    @set:PropertyName("app_name")
    var appName: String = "",

    @get:PropertyName("package_name")
    @set:PropertyName("package_name")
    var packageName: String = "",

    var category: String = "Unknown",

    var confidence: Double = 0.5,

    var duration: Long = 0L,

    var timestamp: Long = 0L
)
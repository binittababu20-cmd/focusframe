package com.focusframe.monitor

data class ClassificationResult(
    val category: String,
    val confidence: Double
)

object AppClassifier {

    // =========================================================
    // EDUCATIONAL APPS
    // =========================================================

    private val educationalApps = mapOf(

        // ─── Google Workspace / Productivity ──────────────────
        "com.google.android.apps.classroom"              to 0.95,
        "com.google.android.apps.meetings"               to 0.90,
        "com.google.android.apps.docs"                   to 0.85,
        "com.google.android.apps.slides"                 to 0.85,
        "com.google.android.apps.sheets"                 to 0.85,
        "com.google.android.apps.docs.editors.docs"      to 0.95,
        "com.google.android.apps.docs.editors.slides"    to 0.95,
        "com.google.android.apps.docs.editors.sheets"    to 0.95,

        // ─── Microsoft ─────────────────────────────────────────
        "com.microsoft.teams"                            to 0.90,
        "com.microsoft.office.word"                      to 0.85,
        "com.microsoft.office.excel"                     to 0.85,
        "com.microsoft.office.powerpoint"                to 0.85,

        // ─── Video Conferencing ────────────────────────────────
        "us.zoom.videomeetings"                          to 0.88,

        // ─── Online Learning Platforms ─────────────────────────
        "org.khanacademy.android"                        to 0.97,
        "com.coursera.android"                           to 0.97,
        "com.duolingo"                                   to 0.93,
        "org.edx.mobile"                                 to 0.97,
        "com.udemy.android"                              to 0.95,
        "com.microblink.photomath"                       to 0.95,
        "com.wolfram.android.alpha"                      to 0.92,
        "com.quizlet.quizletandroid"                     to 0.93,
        "com.ichi2.anki"                                 to 0.94,
        "com.desmos.calculator"                          to 0.92,
        "org.geogebra.android"                           to 0.93,
        "org.wikipedia"                                  to 0.88,

        // ─── Note-Taking / Organisation ────────────────────────
        "notion.id"                                      to 0.82,
        "com.evernote"                                   to 0.80
    )


    // =========================================================
    // NON-EDUCATIONAL / SOCIAL / ENTERTAINMENT APPS
    // =========================================================

    private val nonEducationalApps = mapOf(

        // ─── Social Media ──────────────────────────────────────
        "com.instagram.android"                          to 0.98,
        "com.snapchat.android"                           to 0.98,
        "com.zhiliaoapp.musically"                       to 0.99,
        "com.facebook.katana"                            to 0.98,
        "com.twitter.android"                            to 0.95,
        "com.reddit.frontpage"                           to 0.92,

        // ─── Messaging (personal / non-school) ─────────────────
        "com.whatsapp"                                   to 0.90,
        "org.telegram.messenger"                         to 0.88,
        "com.discord"                                    to 0.87,
        "com.google.android.apps.tachyon"                to 0.90,

        // ─── Video / Audio Entertainment ───────────────────────
        "com.google.android.youtube"                     to 0.85,
        "com.netflix.mediaclient"                        to 0.97,
        "com.spotify.music"                              to 0.90,

        // ─── Gaming ────────────────────────────────────────────
        "com.tencent.ig"                                 to 0.99,
        "com.dts.freefireth"                             to 0.99,
        "com.supercell.clashofclans"                     to 0.99,
        "com.pubg.imobile"                               to 0.99,

        // ─── Shopping ──────────────────────────────────────────
        "com.amazon.mShop.android.shopping"              to 0.92,
        "com.flipkart.android"                           to 0.93,
        "com.meesho.supply"                              to 0.93,
        "com.myntra.android"                             to 0.93
    )


    // =========================================================
    // NEUTRAL / SYSTEM APPS
    // (returned as "Neutral" — not counted toward focus score)
    // =========================================================

    private val neutralApps = mapOf(
        "com.google.android.calculator"                  to 1.0,
        "com.google.android.deskclock"                   to 1.0,
        "com.android.camera2"                            to 1.0,
        "com.android.settings"                           to 1.0
    )


    // =========================================================
    // CLASSIFY
    // =========================================================

    fun classify(packageName: String): ClassificationResult {

        educationalApps[packageName]?.let { confidence ->
            return ClassificationResult(
                category   = "Educational",
                confidence = confidence
            )
        }

        nonEducationalApps[packageName]?.let { confidence ->
            return ClassificationResult(
                category   = "Non-Educational",
                confidence = confidence
            )
        }

        neutralApps[packageName]?.let { confidence ->
            return ClassificationResult(
                category   = "Neutral",
                confidence = confidence
            )
        }

        return ClassificationResult(
            category   = "Unknown",
            confidence = 0.50
        )
    }
}

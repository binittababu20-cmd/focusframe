package com.focusframe.monitor

object FocusScoreCalculator {

    fun calculate(
        educationalDuration: Long,
        totalDuration: Long
    ): Double {

        if (totalDuration <= 0L) {
            return 0.0
        }

        val score =
            (educationalDuration.toDouble() /
                    totalDuration.toDouble()) * 100.0

        return score.coerceIn(0.0, 100.0)
    }

    fun getFocusLevel(score: Double): String {

        return when {
            score >= 80.0 -> "Highly Focused"
            score >= 60.0 -> "Moderately Focused"
            else -> "Low Focus"
        }
    }
}
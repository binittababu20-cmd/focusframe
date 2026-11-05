package com.focusframe.monitor.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat

// FocusFrame Website Shape Scale (Matches website card border-radius: 16-18px and button radius: 10px)
val AppShapes = Shapes(
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(18.dp)
)

private val DarkColorScheme = darkColorScheme(
    primary = FocusBlueHover,
    onPrimary = Color.White,
    primaryContainer = Color(0xFF1E3A8A),
    onPrimaryContainer = Color(0xFFDBEAFE),

    secondary = Navy,
    onSecondary = Color.White,
    secondaryContainer = DarkSurfaceVariant,
    onSecondaryContainer = Color(0xFFE2E8F0),

    tertiary = Gold,
    onTertiary = Navy,
    tertiaryContainer = Color(0xFF78350F),
    onTertiaryContainer = Color(0xFFFEF3C7),

    background = DarkBg,
    onBackground = TextLight,

    surface = DarkSurface,
    onSurface = TextLight,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = TextLightSecondary,

    outline = DarkBorder,
    outlineVariant = Color(0xFF475569),

    error = DangerRed,
    onError = Color.White,
    errorContainer = Color(0xFF450A0A),
    onErrorContainer = Color(0xFFFECACA)
)

private val LightColorScheme = lightColorScheme(
    primary = FocusBlue,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFEFF3FD),
    onPrimaryContainer = Navy,

    secondary = Navy,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFEDF2F7),
    onSecondaryContainer = Navy,

    tertiary = Gold,
    onTertiary = Navy,
    tertiaryContainer = WarningGoldLight,
    onTertiaryContainer = WarningGoldText,

    background = PageBgLight,
    onBackground = Navy,

    surface = CardBgLight,
    onSurface = Navy,
    surfaceVariant = BorderSubtle,
    onSurfaceVariant = SlateText,

    outline = BorderLight,
    outlineVariant = Color(0xFFCBD5E1),

    error = DangerRed,
    onError = Color.White,
    errorContainer = DangerRedLight,
    onErrorContainer = DangerRedText
)

@Composable
fun FocusFrameMonitorTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // Keep dynamicColor false by default to ensure the website brand colors are rendered
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as? Activity)?.window
            if (window != null) {
                window.statusBarColor = if (darkTheme) DarkBg.toArgb() else Color.White.toArgb()
                WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
            }
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        shapes = AppShapes,
        content = content
    )
}
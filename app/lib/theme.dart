import 'package:flutter/material.dart';

/// Paleta aplicatiei: albastru-noapte cu accent indigo.
///
/// Culorile pentru 1 / X / 2 sunt alese sa se distinga si pentru cineva cu
/// daltonism rosu-verde: indigo deschis, gri-ardezie si chihlimbar difera
/// destul de mult ca luminozitate, nu doar ca nuanta.
abstract final class AppColors {
  static const background = Color(0xFF0B0F1A);
  static const surface = Color(0xFF151B2B);
  static const surfaceHigh = Color(0xFF1F2738);
  static const border = Color(0xFF252F45);

  static const accent = Color(0xFF6366F1);
  static const accentSoft = Color(0xFF818CF8);

  static const homeWin = Color(0xFF818CF8);
  static const draw = Color(0xFF94A3B8);
  static const awayWin = Color(0xFFFBBF24);

  static const positive = Color(0xFF34D399);
  static const negative = Color(0xFFF87171);
  static const warning = Color(0xFFFBBF24);

  static const textPrimary = Color(0xFFE8EBF2);
  static const textSecondary = Color(0xFF8B97AD);
}

ThemeData buildTheme() {
  const scheme = ColorScheme.dark(
    primary: AppColors.accent,
    secondary: AppColors.accentSoft,
    surface: AppColors.surface,
    onSurface: AppColors.textPrimary,
    error: AppColors.negative,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.background,
    dividerColor: AppColors.border,
    cardTheme: CardThemeData(
      color: AppColors.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      // Un contur de un pixel separa cardul de fundal mai curat decat o umbra.
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppColors.border),
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.background,
      surfaceTintColor: Colors.transparent,
      centerTitle: false,
      iconTheme: IconThemeData(color: AppColors.textPrimary),
    ),
    textTheme: const TextTheme(
      titleLarge: TextStyle(fontWeight: FontWeight.w600, color: AppColors.textPrimary),
      titleMedium: TextStyle(fontWeight: FontWeight.w600, color: AppColors.textPrimary),
      bodyMedium: TextStyle(color: AppColors.textPrimary, height: 1.4),
      bodySmall: TextStyle(color: AppColors.textSecondary, height: 1.4),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surfaceHigh,
      isDense: true,
      hintStyle: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: AppColors.surface,
      selectedColor: AppColors.accent.withValues(alpha: 0.24),
      side: const BorderSide(color: AppColors.border),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
      labelStyle: const TextStyle(color: AppColors.textPrimary),
    ),
  );
}

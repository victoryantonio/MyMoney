/// Token warna aplikasi (DESIGN.md §9) — dipakai lintas layar agar
/// konsisten dengan spesifikasi desain (income hijau, expense merah,
/// net biru — sama seperti v1 Kotlin).
library;

import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // Light mode
  static const incomeLight = Color(0xFF3D7A5F);
  static const expenseLight = Color(0xFFA8503C);
  static const netLight = Color(0xFF3B5B8C);

  // Dark mode
  static const incomeDark = Color(0xFF6AAF8E);
  static const expenseDark = Color(0xFFD18871);
  static const netDark = Color(0xFF7B9ED4);

  static Color income(BuildContext context) => Theme.of(context).brightness ==
          Brightness.dark
      ? incomeDark
      : incomeLight;

  static Color expense(BuildContext context) =>
      Theme.of(context).brightness == Brightness.dark ? expenseDark : expenseLight;

  static Color net(BuildContext context) =>
      Theme.of(context).brightness == Brightness.dark ? netDark : netLight;
}

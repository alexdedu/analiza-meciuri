import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/home_screen.dart';
import 'package:intl/date_symbol_data_local.dart';

/// Antetul de zi trebuie sa fie usor de gasit dintr-o privire: intr-o fereastra
/// de trei zile, "AZI" conteaza mai mult decat data calendaristica.
void main() {
  setUpAll(() => initializeDateFormatting('ro'));

  Future<void> pump(WidgetTester tester, DateTime zi) => tester.pumpWidget(
        MaterialApp(home: Scaffold(body: DayHeader(day: zi))),
      );

  testWidgets('ziua curenta e marcata cu AZI', (tester) async {
    await pump(tester, DateTime.now());
    expect(find.text('AZI'), findsOneWidget);
  });

  testWidgets('ziua urmatoare e marcata cu MÂINE', (tester) async {
    await pump(tester, DateTime.now().add(const Duration(days: 1)));
    expect(find.text('MÂINE'), findsOneWidget);
  });

  testWidgets('o zi mai indepartata nu primeste eticheta', (tester) async {
    await pump(tester, DateTime.now().add(const Duration(days: 2)));
    expect(find.text('AZI'), findsNothing);
    expect(find.text('MÂINE'), findsNothing);
  });

  testWidgets('data e scrisa in romana, cu majuscula', (tester) async {
    await pump(tester, DateTime(2026, 9, 18));
    expect(find.textContaining('septembrie'), findsOneWidget);
    final text = tester.widget<Text>(find.textContaining('septembrie'));
    expect(text.data![0], text.data![0].toUpperCase());
  });

  testWidgets('data foloseste culoarea de evidentiere, nu textul obisnuit',
      (tester) async {
    await pump(tester, DateTime(2026, 9, 18));
    final text = tester.widget<Text>(find.textContaining('septembrie'));
    expect(text.style?.color, const Color(0xFFFBBF24));
    expect(text.style?.fontSize, greaterThanOrEqualTo(15));
  });
}

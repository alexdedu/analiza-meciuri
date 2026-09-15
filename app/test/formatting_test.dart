import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/formatting.dart';

/// Bannerul afiseaza "<vechime> · <sursa>". Cele doua parti nu trebuie sa spuna
/// acelasi lucru, altfel iese "actualizat acum 14 min · actualizat acum".
void main() {
  final acum = DateTime(2026, 9, 15, 20, 0);

  String label(Duration vechime) =>
      freshnessLabel(acum.subtract(vechime), now: acum);

  test('minute', () {
    expect(label(const Duration(minutes: 14)), 'date de acum 14 min');
    expect(label(const Duration(minutes: 59)), 'date de acum 59 min');
  });

  test('sub un minut', () {
    expect(label(const Duration(seconds: 20)), 'date de acum cateva secunde');
  });

  test('ore', () {
    expect(label(const Duration(hours: 1)), 'date de acum 1 h');
    expect(label(const Duration(hours: 23)), 'date de acum 23 h');
  });

  test('zile', () {
    expect(label(const Duration(days: 1)), 'date de ieri');
    expect(label(const Duration(days: 4)), 'date de acum 4 zile');
  });

  test('ceas nepotrivit: data din viitor nu produce text negativ', () {
    expect(label(const Duration(minutes: -5)), 'date proaspete');
  });

  test('nu repeta cuvantul din eticheta sursei', () {
    for (final d in [
      const Duration(minutes: 3),
      const Duration(hours: 5),
      const Duration(days: 2),
    ]) {
      expect(label(d).contains('actualizat'), isFalse);
    }
  });
}

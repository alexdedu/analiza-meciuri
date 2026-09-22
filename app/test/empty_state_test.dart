import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/home_screen.dart';
import 'package:football_predictor/models.dart';
import 'package:intl/date_symbol_data_local.dart';

/// O listă goală poate insemna doua lucruri opuse: pauza sau defectiune.
/// Daca aplicatia nu le deosebeste, utilizatorul crede ca s-a stricat.
Future<void> pump(WidgetTester tester, NextRound? r) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: Center(child: EmptyState(nextRound: r))),
  ));
  await tester.pumpAndSettle();
}

DateTime cuZile(int zile) {
  final a = DateTime.now();
  return DateTime(a.year, a.month, a.day).add(Duration(days: zile));
}

void main() {
  setUpAll(() => initializeDateFormatting('ro'));

  testWidgets('in pauza spune cand se reiau meciurile', (tester) async {
    await pump(
        tester,
        NextRound(date: cuZile(18), competitions: const ['Premier League']));

    expect(find.text('Pauză competițională'), findsOneWidget);
    expect(find.textContaining('peste 18 zile'), findsOneWidget);
    expect(find.text('Premier League'), findsOneWidget);
  });

  testWidgets('arata data, nu doar numarul de zile', (tester) async {
    final cand = cuZile(18);
    await pump(tester, NextRound(date: cand, competitions: const []));
    // Ziua din luna apare in antetul de data, oricare ar fi luna.
    expect(find.textContaining('${cand.day}'), findsWidgets);
  });

  testWidgets('fara informatie despre pauza, nu inventeaza una',
      (tester) async {
    await pump(tester, null);
    expect(find.textContaining('Niciun meci în următoarele 3 zile'),
        findsOneWidget);
    expect(find.text('Pauză competițională'), findsNothing);
  });

  test('o pauza fara data nu se transforma in obiect', () {
    expect(NextRound.fromJson(null), isNull);
    expect(NextRound.fromJson(const {'date': null, 'competitions': []}), isNull);
    expect(
        NextRound.fromJson(const {
          'date': '2026-10-10',
          'competitions': ['La Liga']
        })!.competitions,
        ['La Liga']);
  });
}

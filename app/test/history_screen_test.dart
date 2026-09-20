import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/history_screen.dart';
import 'package:football_predictor/models.dart';
import 'package:intl/date_symbol_data_local.dart';

/// Ecranul asta e dovada bilantului. Daca ascunde o selectie pierduta sau
/// scrie alt scor decat cel primit, tot restul aplicatiei devine nedemn de
/// incredere, asa ca verificam fiecare stare in parte.
/// Zilele se calculeaza fata de ceasul de acum: un meci "de maine" scris ca
/// data fixa devine trecut peste o saptamana, iar testul ar incepe sa cada.
DateTime cuZile(int zile) {
  final a = DateTime.now();
  return DateTime(a.year, a.month, a.day).add(Duration(days: zile));
}

SelectionRecord sel({
  String matchId = 'M1',
  DateTime? date,
  String home = 'Gazda',
  String away = 'Oaspete',
  bool? won,
  String? score,
  double odds = 1.50,
}) =>
    SelectionRecord(
      matchId: matchId,
      date: date ?? cuZile(-2),
      leagueName: 'Primeira Liga',
      home: home,
      away: away,
      marketLabel: 'Victorie $home',
      probability: 0.72,
      odds: odds,
      band: '70-80%',
      won: won,
      score: score,
    );

TrackRecord record(List<SelectionRecord> selections,
        {int resolved = 1, int hits = 1, double? rata = 1.0, double? profit = 0.5}) =>
    TrackRecord(
      total: selections.length,
      resolved: resolved,
      pending: selections.length - resolved,
      hits: hits,
      hitRate: rata,
      profitUnits: profit,
      roi: 0.5,
      bands: const [],
      since: '2026-09-18',
      selections: selections,
    );

Future<void> pump(WidgetTester tester, TrackRecord r) async {
  await tester.pumpWidget(MaterialApp(home: HistoryScreen(record: r)));
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(() => initializeDateFormatting('ro'));

  testWidgets('arata scorul si castigul pentru o selectie reusita',
      (tester) async {
    await pump(tester,
        record([sel(won: true, score: '2-0', odds: 1.50)], profit: 3.25));
    expect(find.text('Gazda – Oaspete'), findsOneWidget);
    expect(find.text('2-0'), findsOneWidget);
    expect(find.text('+0.50u'), findsOneWidget);
  });

  testWidgets('nu ascunde o selectie pierduta', (tester) async {
    await pump(tester,
        record([sel(won: false, score: '0-1')],
            hits: 0, rata: 0.0, profit: -4.50));
    expect(find.text('0-1'), findsOneWidget);
    expect(find.text('-1.00u'), findsOneWidget);
  });

  testWidgets('un meci care nu s-a jucat inca nu primeste nici scor, nici profit',
      (tester) async {
    await pump(tester,
        record([sel(date: cuZile(2))],
            resolved: 0, hits: 0, rata: null, profit: null));
    expect(find.text('nejucat'), findsOneWidget);
    expect(find.text('—'), findsWidgets);
  });

  testWidgets('un meci jucat, dar fara scor in date, spune ca asteapta',
      (tester) async {
    // Rezultatele apar in sursa cu o zi-doua intarziere. Pana atunci, "nejucat"
    // ar fi o minciuna.
    await pump(tester,
        record([sel(date: cuZile(-1))],
            resolved: 0, hits: 0, rata: null, profit: null));
    expect(find.text('așteaptă scorul'), findsOneWidget);
    expect(find.text('nejucat'), findsNothing);
  });

  testWidgets('filtrul pe jucate lasa deoparte meciurile viitoare',
      (tester) async {
    await pump(
      tester,
      record([
        sel(matchId: 'A', home: 'Jucat', won: true, score: '3-1'),
        sel(matchId: 'B', home: 'Viitor', date: cuZile(5)),
      ]),
    );
    expect(find.text('Jucat – Oaspete'), findsOneWidget);
    expect(find.text('Viitor – Oaspete'), findsOneWidget);

    await tester.tap(find.textContaining('Jucate (1)'));
    await tester.pumpAndSettle();

    expect(find.text('Jucat – Oaspete'), findsOneWidget);
    expect(find.text('Viitor – Oaspete'), findsNothing);
  });

  testWidgets('lista goala spune de ce e goala', (tester) async {
    await pump(tester, record(const [], resolved: 0, hits: 0, rata: null, profit: null));
    expect(find.textContaining('Încă nu s-a notat nicio selecție'), findsOneWidget);
  });
}

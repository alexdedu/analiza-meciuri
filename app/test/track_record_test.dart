import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/models.dart';
import 'package:football_predictor/track_record_card.dart';

/// Bilantul trebuie sa spuna adevarul si cand e gol, si cand e slab.
TrackRecord record({
  int total = 20,
  int resolved = 12,
  int hits = 9,
  double? hitRate = 0.75,
  double? profit = 1.4,
  List<BandRecord> bands = const [],
  List<SelectionRecord> selections = const [],
}) =>
    TrackRecord(
      total: total,
      resolved: resolved,
      pending: total - resolved,
      hits: hits,
      hitRate: hitRate,
      profitUnits: profit,
      roi: 0.1,
      bands: bands,
      since: '2026-09-18',
      selections: selections,
    );

SelectionRecord selectie({
  String matchId = 'M1',
  String date = '2026-09-19',
  String home = 'Gazda',
  String away = 'Oaspete',
  bool? won,
  String? score,
  double odds = 1.50,
}) =>
    SelectionRecord(
      matchId: matchId,
      date: DateTime.parse(date),
      leagueName: 'Test',
      home: home,
      away: away,
      marketLabel: 'Victorie $home',
      probability: 0.72,
      odds: odds,
      band: '70-80%',
      won: won,
      score: score,
    );

Future<void> pump(WidgetTester tester, TrackRecord r) => tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(child: TrackRecordCard(record: r)),
        ),
      ),
    );

void main() {
  testWidgets('arata rata si cate selectii stau in spatele ei', (tester) async {
    await pump(tester, record());
    expect(find.text('75%'), findsOneWidget);
    expect(find.textContaining('9 din 12 reușite'), findsOneWidget);
  });

  testWidgets('arata profitul la miza fixa', (tester) async {
    await pump(tester, record(profit: 1.4));
    expect(find.text('+1.40u'), findsOneWidget);
  });

  testWidgets('profitul negativ nu e ascuns', (tester) async {
    await pump(tester, record(profit: -3.25));
    expect(find.text('-3.25u'), findsOneWidget);
  });

  testWidgets('fara rezultate spune ca se asteapta, nu arata zero fals',
      (tester) async {
    await pump(tester, record(resolved: 0, hits: 0, hitRate: null, profit: null));
    expect(find.textContaining('niciun meci încheiat'), findsOneWidget);
    expect(find.text('0%'), findsNothing);
  });

  testWidgets('pe benzi compara realizatul cu ce promitea backtestul',
      (tester) async {
    await pump(tester, record(bands: const [
      BandRecord(band: '70-80%', count: 12, hits: 9, rate: 0.75, expected: 0.753),
    ]));
    expect(find.text('70-80%'), findsOneWidget);
    expect(find.text('9/12'), findsOneWidget);
    expect(find.textContaining('promis 75%'), findsOneWidget);
  });

  testWidgets('sub 30 de rezultate avertizeaza ca e prea devreme',
      (tester) async {
    await pump(tester, record(resolved: 12));
    expect(find.textContaining('mai degrabă noroc decât semnal'), findsOneWidget);
  });

  testWidgets('ofera drumul catre lista selectiilor', (tester) async {
    await pump(tester, record(selections: [selectie(), selectie(matchId: 'M2')]));
    expect(find.textContaining('Vezi toate selecțiile (2)'), findsOneWidget);
  });

  testWidgets('drumul apare si cand niciun meci nu s-a jucat inca',
      (tester) async {
    await pump(
        tester,
        record(
          resolved: 0,
          hits: 0,
          hitRate: null,
          profit: null,
          selections: [selectie()],
        ));
    expect(find.textContaining('Vezi toate selecțiile (1)'), findsOneWidget);
  });

  testWidgets('fara selectii nu promite o lista care nu exista', (tester) async {
    await pump(tester, record());
    expect(find.textContaining('Vezi toate selecțiile'), findsNothing);
  });
}

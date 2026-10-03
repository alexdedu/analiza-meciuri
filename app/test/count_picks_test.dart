import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/count_picks_card.dart';
import 'package:football_predictor/models.dart';

/// Sectiunea asta promite mai putin decat celelalte, si trebuie sa se vada:
/// pentru cornere si cartonase nu exista cote, deci nici randament.
CountPick pick({
  String matchId = 'M1',
  String label = 'Dortmund — mai multe cornere',
  double probability = 0.70,
  double fairOdds = 1.43,
  double hitRate = 0.649,
}) =>
    CountPick(
      matchId: matchId,
      leagueName: 'Bundesliga',
      date: '2026-10-09',
      time: '18:30',
      home: 'Dortmund',
      away: 'Werder Bremen',
      marketLabel: label,
      probability: probability,
      fairOdds: fairOdds,
      historicalHitRate: hitRate,
    );

Future<void> pump(WidgetTester tester, List<CountPick> picks,
        {CountsRecord? record}) =>
    tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: CountPicksCard(picks: picks, record: record, onTap: (_) {}),
        ),
      ),
    ));

void main() {
  testWidgets('arata pariul, procentul si cota corecta', (tester) async {
    await pump(tester, [pick()]);
    expect(find.text('Dortmund — mai multe cornere'), findsOneWidget);
    expect(find.text('70%'), findsOneWidget);
    expect(find.textContaining('Cotă corectă 1.43'), findsOneWidget);
  });

  testWidgets('spune ca nu exista cote pentru pietele astea', (tester) async {
    await pump(tester, [pick()]);
    expect(find.textContaining('nu există cote nicăieri'), findsOneWidget);
  });

  testWidgets('fara selectii nu lasa un card gol in pagina', (tester) async {
    await pump(tester, []);
    expect(find.textContaining('Cornere și cartonașe'), findsNothing);
  });

  testWidgets('bilantul apare doar dupa ce s-a verificat ceva', (tester) async {
    await pump(tester, [pick()],
        record: const CountsRecord(
            total: 4, resolved: 0, pending: 4, hits: 0,
            hitRate: null, expected: 0.65));
    expect(find.textContaining('Până acum'), findsNothing);

    await pump(tester, [pick()],
        record: const CountsRecord(
            total: 10, resolved: 8, pending: 2, hits: 5,
            hitRate: 0.625, expected: 0.65));
    expect(find.textContaining('5 din 8'), findsOneWidget);
    expect(find.text('63%'), findsOneWidget);
    expect(find.textContaining('promis 65%'), findsOneWidget);
  });

  testWidgets('apasarea duce catre meciul corect', (tester) async {
    String? apasat;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: CountPicksCard(
          picks: [pick(matchId: 'MECI_7')],
          record: null,
          onTap: (id) => apasat = id,
        ),
      ),
    ));
    await tester.tap(find.text('Dortmund — mai multe cornere'));
    expect(apasat, 'MECI_7');
  });

  test('bilantul gol nu se transforma in obiect', () {
    expect(CountsRecord.fromJson(null), isNull);
    expect(CountsRecord.fromJson(const {'total': 0}), isNull);
  });
}

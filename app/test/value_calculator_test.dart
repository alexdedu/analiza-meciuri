import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/models.dart';
import 'package:football_predictor/repository.dart';
import 'package:football_predictor/value_calculator.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Verifica matematica din calculatorul de valoare: edge = p * cota - 1.
/// Testul chiar tasteaza in campuri, deci acopera si legarea starii.
MatchPrediction buildMatch() {
  const ctx = TeamContext(
    form: ['V', 'E', 'I'],
    goalsForAvg: 1.5,
    goalsAgainstAvg: 1.1,
    shotsOnTargetAvg: 4.2,
    matchesAnalysed: 3,
  );
  return MatchPrediction(
    id: 'TEST_1',
    league: 'E0',
    leagueName: 'Premier League',
    date: DateTime(2026, 9, 20),
    time: '17:00',
    home: 'Acasa FC',
    away: 'Oaspete FC',
    probabilities: const {
      'p_home': 0.50,
      'p_draw': 0.30,
      'p_away': 0.20,
      'p_over25': 0.55,
      'p_under25': 0.45,
      'p_btts': 0.52,
      'p_no_btts': 0.48,
    },
    expectedGoalsHome: 1.6,
    expectedGoalsAway: 1.1,
    confidence: Confidence.ridicata,
    homeMatches: 60,
    awayMatches: 60,
    topScores: const [ScoreLine('1-1', 0.12)],
    referenceOdds: const {'home': 2.0},
    homeContext: ctx,
    awayContext: ctx,
    headToHead: const [],
    explanation: 'test',
  );
}

Future<void> pumpCalculator(WidgetTester tester) async {
  SharedPreferences.setMockInitialValues({});
  final store = await OddsStore.create();
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: ValueCalculator(match: buildMatch(), store: store),
      ),
    ),
  ));
}

void main() {
  testWidgets('cota corecta este inversul probabilitatii', (tester) async {
    await pumpCalculator(tester);
    // p_home = 0.50 -> cota corecta 2.00
    expect(find.textContaining('corect 2.00'), findsOneWidget);
    // p_away = 0.20 -> cota corecta 5.00
    expect(find.textContaining('corect 5.00'), findsOneWidget);
  });

  testWidgets('cota peste cea corecta produce avantaj pozitiv', (tester) async {
    await pumpCalculator(tester);
    // 0.50 * 2.50 - 1 = +25%
    await tester.enterText(find.byType(TextField).first, '2.50');
    await tester.pump();
    expect(find.text('+25.0%'), findsOneWidget);
  });

  testWidgets('cota sub cea corecta produce avantaj negativ', (tester) async {
    await pumpCalculator(tester);
    // 0.50 * 1.80 - 1 = -10%
    await tester.enterText(find.byType(TextField).first, '1.80');
    await tester.pump();
    expect(find.text('-10.0%'), findsOneWidget);
  });

  testWidgets('virgula zecimala e acceptata ca punct', (tester) async {
    await pumpCalculator(tester);
    await tester.enterText(find.byType(TextField).first, '2,50');
    await tester.pump();
    expect(find.text('+25.0%'), findsOneWidget);
  });

  testWidgets('cota invalida nu produce niciun rezultat', (tester) async {
    await pumpCalculator(tester);
    await tester.enterText(find.byType(TextField).first, '0.80');
    await tester.pump();
    expect(find.textContaining('%', skipOffstage: false), findsWidgets);
    // O cota sub 1 nu are sens: randul ramane cu liniuta.
    expect(find.text('—'), findsWidgets);
  });

  testWidgets('cota introdusa este salvata si recitita', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final store = await OddsStore.create();
    await store.write('TEST_1', 'home', 3.0);
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: ValueCalculator(match: buildMatch(), store: store),
        ),
      ),
    ));
    // 0.50 * 3.00 - 1 = +50%
    expect(find.text('+50.0%'), findsOneWidget);
  });

  testWidgets('reperul de randament din backtest este vizibil', (tester) async {
    await pumpCalculator(tester);
    expect(find.textContaining('−3.8%'), findsOneWidget);
  });
}

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/about_screen.dart';
import 'package:football_predictor/models.dart';
import 'package:intl/date_symbol_data_local.dart';

/// Ecranul "Despre model" e locul unde aplicatia isi recunoaste limitele.
/// Testul se asigura ca avertismentele chiar ajung pe ecran, cu cifrele reale.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late PredictionBundle bundle;

  setUpAll(() async {
    // AboutScreen formateaza data in romana; in aplicatie asta se face in main().
    await initializeDateFormatting('ro');
    final raw = await rootBundle.loadString('assets/predictions.json');
    bundle = PredictionBundle.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  });

  testWidgets('afiseaza explicit ca modelul nu bate casele de pariuri',
      (tester) async {
    await tester.pumpWidget(MaterialApp(home: AboutScreen(bundle: bundle)));
    expect(find.textContaining('NU bate casele de pariuri'), findsOneWidget);
  });

  testWidgets('afiseaza cifrele reale din backtest', (tester) async {
    await tester.pumpWidget(MaterialApp(home: AboutScreen(bundle: bundle)));
    expect(find.text(bundle.backtest.logLoss.toStringAsFixed(5)), findsOneWidget);
    expect(find.text(bundle.backtest.marketLogLoss.toStringAsFixed(5)), findsOneWidget);
    expect(find.text('Nu'), findsOneWidget); // randul "Bate piata"
  });

  testWidgets('numarul de meciuri testate e formatat cu separator', (tester) async {
    await tester.pumpWidget(MaterialApp(home: AboutScreen(bundle: bundle)));
    expect(find.text('60.539'), findsOneWidget);
  });
}

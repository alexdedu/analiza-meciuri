import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'home_screen.dart';
import 'notificari.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Numele zilelor si lunilor in romana, pentru anteturile din lista de meciuri.
  await initializeDateFormatting('ro');
  runApp(const FootballPredictorApp());

  // Dupa ce porneste interfata, ca o problema la notificari sa nu blocheze
  // aplicatia: in cel mai rau caz, nu vin notificari.
  try {
    await pornesteNotificari();
  } catch (_) {}
}

class FootballPredictorApp extends StatelessWidget {
  const FootballPredictorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Analiza meciuri',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: const HomeScreen(),
    );
  }
}

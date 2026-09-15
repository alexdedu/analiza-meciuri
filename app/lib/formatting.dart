/// Texte scurte pentru starea datelor afisate in banner.
library;

/// Cat de vechi e fisierul de predictii, in cuvinte.
///
/// Se imperecheaza cu eticheta sursei, deci nu trebuie sa contina cuvantul
/// "actualizat" — altfel iese "actualizat acum 14 min · actualizat acum".
String freshnessLabel(DateTime generatedAt, {DateTime? now}) {
  final age = (now ?? DateTime.now()).difference(generatedAt);

  if (age.isNegative) return 'date proaspete';
  if (age.inMinutes < 1) return 'date de acum cateva secunde';
  if (age.inMinutes < 60) return 'date de acum ${age.inMinutes} min';
  if (age.inHours < 24) return 'date de acum ${age.inHours} h';
  if (age.inDays == 1) return 'date de ieri';
  return 'date de acum ${age.inDays} zile';
}

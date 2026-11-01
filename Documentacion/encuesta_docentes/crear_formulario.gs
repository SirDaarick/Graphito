/**
 * Crea el formulario de validación de Graphito con docentes.
 * Uso: script.google.com > Nuevo proyecto > pegar este código > ejecutar crearEncuesta().
 * Al terminar, las direcciones de edición y de respuesta aparecen en Ver > Registros.
 */
function crearEncuesta() {
  const URL_GRAPHITO = 'PEGAR_AQUI_LA_DIRECCION_DE_GRAPHITO';
  const DESACUERDO = 'Totalmente en desacuerdo';
  const ACUERDO = 'Totalmente de acuerdo';

  const form = FormApp.create('Graphito: utilidad para la evaluación de tareas de programación');
  form.setDescription(
    'Esta encuesta forma parte de un proyecto de tesis (IPN, ESCOM). Dura entre 4 y 6 minutos.\n\n' +
    'Participación voluntaria y anónima; las respuestas se usan solo con fines académicos. ' +
    'No se solicita nombre ni correo.\n\n' +
    'Graphito no emite veredictos: muestra información para ayudar a decidir qué entregas revisar primero.\n\n' +
    'Antes de responder, pruebe la plataforma durante 15 a 20 minutos: ' + URL_GRAPHITO
  );
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setAllowResponseEdits(false);
  form.setProgressBar(true);

  form.addMultipleChoiceItem()
    .setTitle('Consentimiento')
    .setChoiceValues(['Acepto participar de forma voluntaria y anónima'])
    .setRequired(true);

  // ---- Sección 1: su proceso actual ----
  form.addPageBreakItem().setTitle('Su proceso actual')
    .setHelpText('Estas dos preguntas describen cómo evalúa hoy, sin Graphito.');

  form.addTextItem()
    .setTitle('1. ¿Cuántos minutos dedica hoy a revisar una entrega típica?')
    .setHelpText('Escriba un número aproximado.')
    .setValidation(FormApp.createTextValidation()
      .setHelpText('Escriba un número mayor o igual a 0.')
      .requireNumberGreaterThanOrEqualTo(0)
      .build())
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('2. ¿Cómo detecta hoy copias entre alumnos o código generado por IA?')
    .setHelpText('Por ejemplo: lectura manual, otra herramienta, preguntas al alumno o ninguna.')
    .setRequired(true);

  // ---- Sección 2: después de probar Graphito ----
  form.addPageBreakItem().setTitle('Después de probar Graphito')
    .setHelpText('Indique qué tan de acuerdo está con cada afirmación (1 = ' + DESACUERDO.toLowerCase() +
      ', 5 = ' + ACUERDO.toLowerCase() + ').');

  const afirmaciones = [
    '3. Graphito me ayudaría a decidir qué entregas revisar primero.',
    '4. Confiaría en el reporte de Graphito como apoyo a mi evaluación (no como calificación).',
    '5. Saber si un código tiene un estilo atípico me sería útil en mi evaluación.'
  ];
  afirmaciones.forEach(function (t) {
    form.addScaleItem().setTitle(t).setBounds(1, 5).setLabels(DESACUERDO, ACUERDO).setRequired(true);
  });

  form.addMultipleChoiceItem()
    .setTitle('6. Con Graphito, ¿cuánto cree que se reduciría el tiempo que dedica a revisar entregas?')
    .setChoiceValues(['0 %', '1 a 25 %', '26 a 50 %', 'Más de 50 %'])
    .setRequired(true);

  form.addScaleItem()
    .setTitle('7. Graphito es fácil de usar.')
    .setBounds(1, 5).setLabels(DESACUERDO, ACUERDO).setRequired(true);

  form.addScaleItem()
    .setTitle('8. Usaría Graphito en mi próximo curso.')
    .setBounds(1, 5).setLabels(DESACUERDO, ACUERDO).setRequired(true);

  form.addParagraphTextItem()
    .setTitle('9. ¿Qué le falta, qué le preocupa o qué cambiaría de Graphito?')
    .setRequired(false);

  form.setConfirmationMessage('Gracias por su participación.');

  Logger.log('Editar: ' + form.getEditUrl());
  Logger.log('Responder: ' + form.getPublishedUrl());
}

"use strict"
@api = @api ? {}
@api.spreadsheet = @api.spreadsheet ? {}
$ = jQuery

@api.spreadsheet.cell = (data, type, style) ->
  type = type or "String"
  if style?
    style = " ss:StyleID=\"" + style + "\""
  else
    style = ""
  "<Cell" + style + "><Data ss:Type=\"" + type + "\">" + data + "</Data></Cell>"

@api.spreadsheet.row = (cell) ->
  "<Row>" + cell + "</Row>"

return

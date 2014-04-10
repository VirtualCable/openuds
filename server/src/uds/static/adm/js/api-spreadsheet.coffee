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


@api.spreadsheet.tableToExcel = (->
  content_type = "application/vnd.ms-excel"
  uri = "data:application/vnd.ms-excel;base64,"
  template = "<html xmlns:o=\"urn:schemas-microsoft-com:office:office\" xmlns:x=\"urn:schemas-microsoft-com:office:excel\" xmlns=\"http://www.w3.org/TR/REC-html40\"><head><meta charset=\"utf-8\"><!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>{worksheet}</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]--></head><body><table>{table}</table></body></html>"
  #base64 = (s) ->
  #  window.btoa unescape(encodeURIComponent(s))

  format = (s, c) ->
    s.replace /{(\w+)}/g, (m, p) ->
      c[p]


  (table, name) ->
    table = document.getElementById(table)  unless table.nodeType
    ctx =
      worksheet: name or "Worksheet"
      table: table.innerHTML

    saveAs new Blob([format(template, ctx)],
                          type: content_type
                        ), name + '.xls'
    # window.location.href = uri + base64(format(template, ctx))
    return
)()

return

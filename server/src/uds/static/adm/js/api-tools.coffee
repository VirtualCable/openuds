# jshint strict: true 
((api, $, undefined_) ->
  "use strict"
  api.tools = 
    base64: (s) ->
      window.btoa unescape(encodeURIComponent(s))
    input2timeStamp: (inputDate, inputTime) ->
      # Just parses date & time in two separate inputs
      # inputTime is in format hours:minutes
      if inputDate is null or inputDate is undefined
        v = new Date(0)
      else
        tmp = inputDate.split('-')
        v = new Date(tmp[0], parseInt(tmp[1])-1, tmp[2])

      if inputTime != null and inputTime != undefined
        tmp = inputTime.split(':')
        if v.getTime() != 0
          v.setHours(tmp[0])
          v.setMinutes(tmp[1])
        else
          return parseInt(tmp[0])*3600 + parseInt(tmp[1]) * 60

      return v.getTime() / 1000


  return
) window.api = window.api or {}, jQuery


# Insert strftime into tools
#
#strftime
#github.com/samsonjs/strftime
#@_sjs
#
#Copyright 2010 - 2013 Sami Samhuri <sami@samhuri.net>
#
#MIT License
#http://sjs.mit-license.org
#
initialsOf = (arr) ->
  res = []
  for v of arr
    res.push arr[v].substr(0, 3)
  res

# Added this to convert django format strings to c format string
# This is ofc, a "simplified" version, aimed to use date format used by
# DJANGO
# daylight saving
# if it is leap year
# Not so sure, not important i thing anyway :-)
# english ordinal suffix for day of month
# number of days of specified month, not important
# microseconds
# Seconds since EPOCH, not used
# Time zone offset in seconds, replaced by offset
# in ours/minutes :-)
strftime = (fmt, d, locale) ->
  _strftime fmt, d, locale

# locale is optional
strftimeTZ = (fmt, d, locale, timezone) ->
  if typeof locale is "number" and not timezone?
    timezone = locale
    locale = null
  _strftime fmt, d, locale,
    timezone: timezone

strftimeUTC = (fmt, d, locale) ->
  _strftime fmt, d, locale,
    utc: true

localizedStrftime = (locale) ->
  (fmt, d, options) ->
    strftime fmt, d, locale, options

# d, locale, and options are optional, but you can't leave
# holes in the argument list. If you pass options you have to pass
# in all the preceding args as well.
#
# options:
# - locale [object] an object with the same structure as DefaultLocale
# - timezone [number] timezone offset in minutes from GMT
_strftime = (fmt, d, locale, options) ->
  options = options or {}
  
  # d and locale are optional so check if d is really the locale
  if d and not quacksLikeDate(d)
    locale = d
    d = null
  d = d or new Date()
  locale = locale or DefaultLocale
  locale.formats = locale.formats or {}
  
  # Hang on to this Unix timestamp because we might mess with it directly
  # below.
  timestamp = d.getTime()
  d = dateToUTC(d)  if options.utc or typeof options.timezone is "number"
  d = new Date(d.getTime() + (options.timezone * 60000))  if typeof options.timezone is "number"
  
  # Most of the specifiers supported by C's strftime, and some from Ruby.
  # Some other syntax extensions from Ruby are supported: %-, %_, and %0
  # to pad with nothing, space, or zero (respectively).
  fmt.replace /%([-_0]?.)/g, (_, c) ->
    mod = null
    padding = null
    if c.length is 2
      mod = c[0]
      
      # omit padding
      if mod is "-"
        padding = ""
      
      # pad with space
      else if mod is "_"
        padding = " "
      
      # pad with zero
      else if mod is "0"
        padding = "0"
      else
        
        # unrecognized, return the format
        return _
      c = c[1]
    switch c
      when "A"
        locale.days[d.getDay()]
      when "a"
        locale.shortDays[d.getDay()]
      when "B"
        locale.months[d.getMonth()]
      when "b"
        locale.shortMonths[d.getMonth()]
      when "C"
        pad Math.floor(d.getFullYear() / 100), padding
      when "D"
        _strftime locale.formats.D or "%m/%d/%y", d, locale
      when "d"
        pad d.getDate(), padding
      when "e"
        d.getDate()
      when "F"
        _strftime locale.formats.F or "%Y-%m-%d", d, locale
      when "H"
        pad d.getHours(), padding
      when "h"
        locale.shortMonths[d.getMonth()]
      when "I"
        pad hours12(d), padding
      when "j"
        y = new Date(d.getFullYear(), 0, 1)
        day = Math.ceil((d.getTime() - y.getTime()) / (1000 * 60 * 60 * 24))
        pad day, 3
      when "k"
        pad d.getHours(), (if padding is undefined then " " else padding)
      when "L"
        pad Math.floor(timestamp % 1000), 3
      when "l"
        pad hours12(d), (if padding is undefined then " " else padding)
      when "M"
        pad d.getMinutes(), padding
      when "m"
        pad d.getMonth() + 1, padding
      when "n"
        "\n"
      when "o"
        String(d.getDate()) + ordinal(d.getDate())
      when "P"
        '' # (if d.getHours() < 12 then locale.am else locale.pm)
      when "p"
        '' # (if d.getHours() < 12 then locale.AM else locale.PM)
      when "R"
        _strftime locale.formats.R or "%H:%M", d, locale
      when "r"
        _strftime locale.formats.r or "%I:%M:%S %p", d, locale
      when "S"
        pad d.getSeconds(), padding
      when "s"
        Math.floor timestamp / 1000
      when "T"
        _strftime locale.formats.T or "%H:%M:%S", d, locale
      when "t"
        "\t"
      when "U"
        pad weekNumber(d, "sunday"), padding
      when "u"
        dayu = d.getDay()
        (if dayu is 0 then 7 else dayu) # 1 - 7, Monday is first day of the
      # week
      when "v"
        _strftime locale.formats.v or "%e-%b-%Y", d, locale
      when "W"
        pad weekNumber(d, "monday"), padding
      when "w"
        d.getDay() # 0 - 6, Sunday is first day of the
      # week
      when "Y"
        d.getFullYear()
      when "y"
        yy = String(d.getFullYear())
        yy.slice yy.length - 2
      when "Z"
        if options.utc
          return "GMT"
        else
          tz = d.toString().match(/\((\w+)\)/)
          return tz and tz[1] or ""
      when "z"
        if options.utc
          return "+0000"
        else
          off_ = (if typeof options.timezone is "number" then options.timezone else -d.getTimezoneOffset())
          return ((if off_ < 0 then "-" else "+")) + pad(Math.abs(off_ / 60)) + pad(off_ % 60)
      else
        c

dateToUTC = (d) ->
  msDelta = (d.getTimezoneOffset() or 0) * 60000
  new Date(d.getTime() + msDelta)
quacksLikeDate = (x) ->
  i = 0
  n = RequiredDateMethods.length
  i = 0
  while i < n
    return false  unless typeof x[RequiredDateMethods[i]] is "function"
    ++i
  true

# Default padding is '0' and default length is 2, both are optional.
pad = (n, padding, length) ->
  
  # pad(n, <length>)
  if typeof padding is "number"
    length = padding
    padding = "0"
  
  # Defaults handle pad(n) and pad(n, <padding>)
  padding ?= "0"
  length ?= 2
  s = String(n)
  
  # padding may be an empty string, don't loop forever if it is
  s = padding + s  while s.length < length  if padding
  s
hours12 = (d) ->
  hour = d.getHours()
  if hour is 0
    hour = 12
  else hour -= 12  if hour > 12
  hour

# Get the ordinal suffix for a number: st, nd, rd, or th
ordinal = (n) ->
  i = n % 10
  ii = n % 100
  return "th"  if (ii >= 11 and ii <= 13) or i is 0 or i >= 4
  switch i
    when 1
      "st"
    when 2
      "nd"
    when 3
      "rd"

# firstWeekday: 'sunday' or 'monday', default is 'sunday'
#
# Pilfered & ported from Ruby's strftime implementation.
weekNumber = (d, firstWeekday) ->
  firstWeekday = firstWeekday or "sunday"
  
  # This works by shifting the weekday back by one day if we
  # are treating Monday as the first day of the week.
  wday = d.getDay()
  if firstWeekday is "monday"
    if wday is 0 # Sunday
      wday = 6
    else
      wday--
  firstDayOfYear = new Date(d.getFullYear(), 0, 1)
  yday = (d - firstDayOfYear) / 86400000
  weekNum = (yday + 7 - wday) / 7
  Math.floor weekNum
"use strict"
namespace = api.tools
dayNames = [
  gettext("Sunday")
  gettext("Monday")
  gettext("Tuesday")
  gettext("Wednesday")
  gettext("Thursday")
  gettext("Friday")
  gettext("Saturday")
]
monthNames = [
  gettext("January")
  gettext("February")
  gettext("March")
  gettext("April")
  gettext("May")
  gettext("June")
  gettext("July")
  gettext("August")
  gettext("September")
  gettext("October")
  gettext("November")
  gettext("December")
]
DefaultLocale =
  days: dayNames
  shortDays: initialsOf(dayNames)
  months: monthNames
  shortMonths: initialsOf(monthNames)
  AM: "AM"
  PM: "PM"
  am: "am"
  pm: "pm"

namespace.djangoFormat = (format) ->
  format.replace /./g, (c) ->
    switch c
      when "a", "A"
        "%p"
      when "b", "d", "m", "w", "W", "y", "Y"
        "%" + c
      when "c"
        "%FT%TZ"
      when "D"
        "%a"
      when "e"
        "%z"
      when "f"
        "%I:%M"
      when "F"
        "%F"
      when "h", "g"
        "%I"
      when "H", "G"
        "%H"
      when "i"
        "%M"
      when "I"
        ""
      when "j"
        "%d"
      when "l"
        "%A"
      when "L"
        ""
      when "M"
        "%b"
      when "n"
        "%m"
      when "N"
        "%b"
      when "o"
        "%W"
      when "O"
        "%z"
      when "P"
        "%R %p"
      when "r"
        "%a, %d %b %Y %T %z"
      when "s"
        "%S"
      when "S"
        ""
      when "t"
        ""
      when "T"
        "%Z"
      when "u"
        "0"
      when "U"
        ""
      when "z"
        "%j"
      when "Z"
        "z"
      else
        c


namespace.strftime = strftime
namespace.strftimeTZ = strftime.strftimeTZ = strftimeTZ
namespace.strftimeUTC = strftime.strftimeUTC = strftimeUTC
namespace.localizedStrftime = strftime.localizedStrftime = localizedStrftime
RequiredDateMethods = [
  "getTime"
  "getTimezoneOffset"
  "getDay"
  "getDate"
  "getMonth"
  "getFullYear"
  "getYear"
  "getHours"
  "getMinutes"
  "getSeconds"
]
return

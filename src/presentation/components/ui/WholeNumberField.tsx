import { useEffect, useRef, useState } from 'react'
import { TextField } from './TextField'

interface WholeNumberFieldProps {
  label: string
  value: number | undefined
  // `undefined` while the input is empty (or just a `-`).
  onChange: (value: number | undefined) => void
  allowNegative?: boolean
  placeholder?: string
  error?: string
  required?: boolean
  helperText?: string
  labelClassName?: string
}

// A `type="number"` input lets a user type `1.5`, `1e3` or `-4` into a count
// the API stores as a whole number, and empties itself on a partial value
// like `-`. This keeps a text draft that only accepts digits (and a leading
// minus when allowed), so a decimal can't be typed at all; the range check
// stays with the form, which knows its limits and message.
export function WholeNumberField({ value, onChange, allowNegative, ...rest }: WholeNumberFieldProps) {
  const [draft, setDraft] = useState(value === undefined ? '' : String(value))
  const lastEmittedRef = useRef(value)

  // A new value from outside (a load, a reset) replaces the draft; the
  // value this field just emitted doesn't, so a transient `-` survives.
  useEffect(() => {
    if (value === lastEmittedRef.current) return
    lastEmittedRef.current = value
    setDraft(value === undefined ? '' : String(value))
  }, [value])

  const pattern = allowNegative ? /^-?\d*$/ : /^\d*$/

  return (
    <TextField
      {...rest}
      value={draft}
      inputMode="numeric"
      onChange={(next) => {
        if (!pattern.test(next)) return
        setDraft(next)
        const parsed = next === '' || next === '-' ? undefined : Number(next)
        lastEmittedRef.current = parsed
        onChange(parsed)
      }}
    />
  )
}

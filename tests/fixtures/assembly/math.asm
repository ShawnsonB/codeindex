; x86-64 NASM assembly — basic math and vector operations

section .data
    pi_approx   dq 3.14159265358979
    euler_e     dq 2.71828182845904

section .bss
    result      resq 1

section .text
    global add_int64
    global multiply_int64
    global clamp_int32
    global compute_dot_product

; Add two 64-bit integers.
; Arguments: rdi = a, rsi = b
; Returns:   rax = a + b
add_int64:
    mov rax, rdi
    add rax, rsi
    ret

; Multiply two 64-bit integers.
; Arguments: rdi = a, rsi = b
; Returns:   rax = low 64 bits of product, rdx = high 64 bits
multiply_int64:
    mov rax, rdi
    imul rsi
    ret

; Clamp a 32-bit integer to [min, max].
; Arguments: edi = value, esi = min, edx = max
; Returns:   eax = clamped value
clamp_int32:
    mov eax, edi
    cmp eax, esi
    cmovl eax, esi
    cmp eax, edx
    cmovg eax, edx
    ret

; Compute dot product of two 3-element float64 vectors.
; Arguments: rdi = pointer to vec_a, rsi = pointer to vec_b
; Returns:   xmm0 = dot product
compute_dot_product:
    movsd xmm0, [rdi]
    mulsd xmm0, [rsi]
    movsd xmm1, [rdi + 8]
    mulsd xmm1, [rsi + 8]
    addsd xmm0, xmm1
    movsd xmm1, [rdi + 16]
    mulsd xmm1, [rsi + 16]
    addsd xmm0, xmm1
    ret

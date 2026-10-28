/* Windows x64 stack guard probing; preserves RAX/RCX and leaves RSP unchanged.
 * Called by compiler before a frame larger than one page. No CRT dependency. */
.text
.globl __chkstk
__chkstk:
    pushq %rcx
    pushq %rax
    leaq 24(%rsp), %rcx
    cmpq $4096, %rax
    jb 2f
1:
    subq $4096, %rcx
    testq %rcx, (%rcx)
    subq $4096, %rax
    cmpq $4096, %rax
    ja 1b
2:
    subq %rax, %rcx
    testq %rcx, (%rcx)
    popq %rax
    popq %rcx
    retq
